"""build_site.py - data/data.json을 읽어 docs/index.html을 만든다.

읽음/안읽음, 즐겨찾기(주요 공지), "관련 공지로 표시" 상태는 서버가 아니라
각 방문자의 브라우저(localStorage)에 저장된다. data.json에는 그 정보가 없고,
브라우저에서 실행되는 JS가 각 공지의 링크를 기준으로 상태를 기억하고,
4개 탭(안 읽은 공지 / 읽은 공지 / 주요 공지 / 다른 학과 공지)으로 나눠 보여준다.

로컬에서 직접 실행할 수도 있다: python src/build_site.py
"""

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "data.json"
OUT_FILE = ROOT / "docs" / "index.html"

STYLE = """
body { font-family: -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 24px; color: #222; }
h1 { margin-bottom: 4px; }
.update-bar { color: #666; font-size: 13px; margin-bottom: 16px; }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }
.tab-btn { font-size: 13px; padding: 6px 12px; border: 1px solid #ccc; border-radius: 999px; background: #fafafa; cursor: pointer; color: #444; }
.tab-btn:hover { background: #eee; }
.tab-btn.active { background: #222; color: #fff; border-color: #222; }
h2 { border-bottom: 2px solid #222; padding-bottom: 4px; margin-top: 32px; }
.site-block.empty-in-tab { display: none; }
.notice-list { list-style: none; padding: 0; margin: 0; }
.notice-item { padding: 8px 0; border-bottom: 1px solid #eee; font-size: 14px; }
.notice-item.tab-hidden { display: none; }
.notice-item.is-read .notice-link { text-decoration: line-through; opacity: 0.7; }
.notice-link { color: #1a4fb4; text-decoration: none; }
.notice-link:hover { text-decoration: underline; }
.meta { color: #888; font-size: 12px; }
.notice-item button { margin-left: 6px; font-size: 12px; padding: 2px 8px; border: 1px solid #ccc; border-radius: 4px; background: #fafafa; cursor: pointer; color: #444; }
.notice-item button:hover { background: #eee; }
.star-btn.is-active { background: #fff3cd; border-color: #e0c060; color: #7a5c00; }
.empty-msg { color: #888; font-size: 14px; padding: 24px 0; }
.error { color: #b00020; font-size: 13px; }
"""

TAB_LABELS = [
    ("unread", "안 읽은 공지"),
    ("read", "읽은 공지"),
    ("starred", "★ 주요 공지"),
    ("other", "다른 학과 공지"),
]

READ_STATE_SCRIPT = """
(function () {
  var READ_KEY = 'inu-notices-read-v1';
  var STAR_KEY = 'inu-notices-starred-v1';
  var OVERRIDE_KEY = 'inu-notices-relevant-override-v1';

  function loadSet(key) {
    try { return new Set(JSON.parse(localStorage.getItem(key) || '[]')); }
    catch (e) { return new Set(); }
  }
  function saveSet(key, set) {
    localStorage.setItem(key, JSON.stringify(Array.from(set)));
  }

  var readSet = loadSet(READ_KEY);
  var starSet = loadSet(STAR_KEY);
  var overrideSet = loadSet(OVERRIDE_KEY);
  var activeTab = 'unread';

  function isRelevant(li) {
    return li.getAttribute('data-relevant') === 'true' || overrideSet.has(li.getAttribute('data-link'));
  }

  function matchesTab(li, tab) {
    var link = li.getAttribute('data-link');
    var relevant = isRelevant(li);
    if (tab === 'other') return !relevant;
    if (!relevant) return false;
    if (tab === 'starred') return starSet.has(link);
    if (tab === 'read') return readSet.has(link);
    return !readSet.has(link); // unread
  }

  function applyItemState(li) {
    var link = li.getAttribute('data-link');
    var serverRelevant = li.getAttribute('data-relevant') === 'true';
    var relevant = isRelevant(li);
    var isRead = readSet.has(link);
    var isStar = starSet.has(link);

    li.classList.toggle('is-read', isRead);

    var readBtn = li.querySelector('.mark-read-btn');
    var starBtn = li.querySelector('.star-btn');
    var relBtn = li.querySelector('.mark-relevant-btn');

    if (readBtn) {
      readBtn.style.display = relevant ? '' : 'none';
      readBtn.textContent = isRead ? '읽지 않음으로 표시' : '읽음으로 표시';
    }
    if (starBtn) {
      starBtn.style.display = relevant ? '' : 'none';
      starBtn.classList.toggle('is-active', isStar);
      starBtn.textContent = isStar ? '★ 주요 공지 해제' : '☆ 주요 공지로 표시';
    }
    if (relBtn) {
      // 원래(서버 기준) 다른 학과 공지였던 것만 이 버튼을 보여준다.
      // 관련 공지로 표시한 뒤에도 계속 보여야 다시 되돌릴 수 있다.
      relBtn.style.display = serverRelevant ? 'none' : '';
      relBtn.textContent = overrideSet.has(link) ? '다른 학과로 되돌리기' : '관련 공지로 표시';
    }
  }

  function refresh() {
    var counts = { unread: 0, read: 0, starred: 0, other: 0 };
    var items = document.querySelectorAll('.notice-item');
    items.forEach(function (li) {
      Object.keys(counts).forEach(function (tab) {
        if (matchesTab(li, tab)) counts[tab]++;
      });
      li.classList.toggle('tab-hidden', !matchesTab(li, activeTab));
    });

    document.querySelectorAll('.tab-btn').forEach(function (btn) {
      var tab = btn.getAttribute('data-tab');
      btn.classList.toggle('active', tab === activeTab);
      var countEl = btn.querySelector('.count');
      if (countEl) countEl.textContent = ' (' + counts[tab] + ')';
    });

    document.querySelectorAll('.site-block').forEach(function (block) {
      var anyVisible = Array.prototype.some.call(
        block.querySelectorAll('.notice-item'),
        function (li) { return matchesTab(li, activeTab); }
      );
      block.classList.toggle('empty-in-tab', !anyVisible);
    });

    var emptyMsg = document.getElementById('empty-msg');
    if (emptyMsg) emptyMsg.style.display = counts[activeTab] === 0 ? '' : 'none';
  }

  document.querySelectorAll('.tab-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      activeTab = btn.getAttribute('data-tab');
      refresh();
    });
  });

  document.querySelectorAll('.notice-item').forEach(function (li) {
    var link = li.getAttribute('data-link');
    applyItemState(li);

    var readBtn = li.querySelector('.mark-read-btn');
    if (readBtn) {
      readBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (readSet.has(link)) readSet.delete(link); else readSet.add(link);
        saveSet(READ_KEY, readSet);
        applyItemState(li);
        refresh();
      });
    }

    var starBtn = li.querySelector('.star-btn');
    if (starBtn) {
      starBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (starSet.has(link)) starSet.delete(link); else starSet.add(link);
        saveSet(STAR_KEY, starSet);
        applyItemState(li);
        refresh();
      });
    }

    var relBtn = li.querySelector('.mark-relevant-btn');
    if (relBtn) {
      relBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (overrideSet.has(link)) overrideSet.delete(link); else overrideSet.add(link);
        saveSet(OVERRIDE_KEY, overrideSet);
        applyItemState(li);
        refresh();
      });
    }

    var a = li.querySelector('.notice-link');
    if (a) {
      a.addEventListener('click', function () {
        if (isRelevant(li) && !readSet.has(link)) {
          readSet.add(link);
          saveSet(READ_KEY, readSet);
          applyItemState(li);
          refresh();
        }
      });
    }
  });

  refresh();
})();
"""


def render_item(n):
    title = html.escape(n["title"])
    link = html.escape(n["link"])
    writer = html.escape(n["writer"])
    date = html.escape(n["date"])
    relevant = "true" if n["relevant"] else "false"
    extra = f" <span class='meta'>- {html.escape(n['matched_dept'])}</span>" if n.get("matched_dept") else ""
    return (
        f"<li class='notice-item' data-link='{link}' data-relevant='{relevant}'>"
        f"<a href='{link}' target='_blank' rel='noopener' class='notice-link'>{title}</a> "
        f"<span class='meta'>{writer} ({date})</span>{extra} "
        f"<button type='button' class='mark-read-btn'>읽음으로 표시</button>"
        f"<button type='button' class='star-btn'>☆ 주요 공지로 표시</button>"
        f"<button type='button' class='mark-relevant-btn'>관련 공지로 표시</button>"
        f"</li>"
    )


def render_site(site):
    parts = [f"<div class='site-block'><h2>{html.escape(site['name'])}</h2>"]

    if site.get("error"):
        parts.append(f"<p class='error'>수집 실패: {html.escape(site['error'])}</p></div>")
        return "\n".join(parts)

    notices = site["notices"]
    if not notices:
        parts.append("<p>아직 수집된 공지가 없습니다.</p></div>")
        return "\n".join(parts)

    parts.append("<ul class='notice-list'>" + "\n".join(render_item(n) for n in notices) + "</ul></div>")
    return "\n".join(parts)


def build():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    meta = data["meta"]
    sites_html = "\n".join(render_site(s) for s in data["sites"])
    keywords = html.escape(", ".join(meta.get("my_keywords", []))) or "(없음)"

    tabs_html = "\n".join(
        f"<button type='button' class='tab-btn{' active' if tab_id == 'unread' else ''}' data-tab='{tab_id}'>"
        f"{html.escape(label)}<span class='count'></span></button>"
        for tab_id, label in TAB_LABELS
    )

    page = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>인천대 알림 모음</title>
<style>{STYLE}</style>
</head>
<body>
<h1>인천대 알림 모음</h1>
<p class="update-bar">마지막 갱신: {html.escape(meta.get('last_updated', ''))} KST · 내 학과 키워드: {keywords}</p>
<div class="tabs">{tabs_html}</div>
<p id="empty-msg" class="empty-msg">이 탭에는 표시할 공지가 없습니다.</p>
{sites_html}
<script>{READ_STATE_SCRIPT}</script>
</body>
</html>"""

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(page, encoding="utf-8")
    print(f"빌드 완료 -> {OUT_FILE}")


if __name__ == "__main__":
    build()
