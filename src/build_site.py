"""build_site.py - data/data.json을 읽어 docs/index.html을 만든다.

읽음/안읽음 상태는 서버가 아니라 각 방문자의 브라우저(localStorage)에 저장된다.
data.json에는 그 정보가 없고, 대신 브라우저에서 실행되는 JS가 각 공지의 링크를
기준으로 "이 링크를 읽음으로 표시했었나"를 기억한다.

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
.update-bar { color: #666; font-size: 13px; margin-bottom: 4px; }
.unread-count { color: #444; font-size: 13px; font-weight: bold; margin-bottom: 24px; }
h2 { border-bottom: 2px solid #222; padding-bottom: 4px; margin-top: 32px; }
h3 { font-size: 15px; color: #444; margin-top: 20px; }
.notice-list { display: flex; flex-direction: column; list-style: none; padding: 0; margin: 0; }
.notice-item { order: 0; padding: 8px 0; border-bottom: 1px solid #eee; font-size: 14px; }
.notice-item.is-read { order: 1; opacity: 0.5; }
.notice-item.is-read .notice-link { text-decoration: line-through; }
.notice-link { color: #1a4fb4; text-decoration: none; }
.notice-link:hover { text-decoration: underline; }
.meta { color: #888; font-size: 12px; }
.mark-read-btn { margin-left: 6px; font-size: 12px; padding: 2px 8px; border: 1px solid #ccc; border-radius: 4px; background: #fafafa; cursor: pointer; color: #444; }
.mark-read-btn:hover { background: #eee; }
details summary { cursor: pointer; color: #666; font-size: 14px; margin-top: 12px; }
.error { color: #b00020; font-size: 13px; }
"""

READ_STATE_SCRIPT = """
(function () {
  var KEY = 'inu-notices-read-v1';

  function loadRead() {
    try { return new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); }
    catch (e) { return new Set(); }
  }
  function saveRead(readSet) {
    localStorage.setItem(KEY, JSON.stringify(Array.from(readSet)));
  }

  var readSet = loadRead();

  function applyState(li) {
    var link = li.getAttribute('data-link');
    var isRead = readSet.has(link);
    li.classList.toggle('is-read', isRead);
    var btn = li.querySelector('.mark-read-btn');
    if (btn) btn.textContent = isRead ? '읽지 않음으로 표시' : '읽음으로 표시';
  }

  function updateCounter() {
    var el = document.getElementById('unread-count');
    if (!el) return;
    var total = document.querySelectorAll('.notice-item').length;
    var unread = document.querySelectorAll('.notice-item:not(.is-read)').length;
    el.textContent = '안 읽은 공지 ' + unread + '건 / 전체 ' + total + '건';
  }

  function toggle(li) {
    var link = li.getAttribute('data-link');
    if (readSet.has(link)) { readSet.delete(link); } else { readSet.add(link); }
    saveRead(readSet);
    applyState(li);
    updateCounter();
  }

  document.querySelectorAll('.notice-item').forEach(function (li) {
    applyState(li);
    var btn = li.querySelector('.mark-read-btn');
    if (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        toggle(li);
      });
    }
    var a = li.querySelector('.notice-link');
    if (a) {
      a.addEventListener('click', function () {
        if (!li.classList.contains('is-read')) toggle(li);
      });
    }
  });

  updateCounter();
})();
"""


def render_item(n):
    title = html.escape(n["title"])
    link = html.escape(n["link"])
    writer = html.escape(n["writer"])
    date = html.escape(n["date"])
    extra = f" <span class='meta'>- {html.escape(n['matched_dept'])}</span>" if n.get("matched_dept") else ""
    return (
        f"<li class='notice-item' data-link='{link}'>"
        f"<a href='{link}' target='_blank' rel='noopener' class='notice-link'>{title}</a> "
        f"<span class='meta'>{writer} ({date})</span>{extra} "
        f"<button type='button' class='mark-read-btn'>읽음으로 표시</button>"
        f"</li>"
    )


def render_site(site):
    parts = [f"<h2>{html.escape(site['name'])}</h2>"]

    if site.get("error"):
        parts.append(f"<p class='error'>수집 실패: {html.escape(site['error'])}</p>")
        return "\n".join(parts)

    notices = site["notices"]
    if not notices:
        parts.append("<p>아직 수집된 공지가 없습니다.</p>")
        return "\n".join(parts)

    relevant = [n for n in notices if n["relevant"]]
    others = [n for n in notices if not n["relevant"]]

    parts.append("<h3>나와 관련된 공지</h3>")
    if relevant:
        parts.append("<ul class='notice-list'>" + "\n".join(render_item(n) for n in relevant) + "</ul>")
    else:
        parts.append("<p>없음</p>")

    if others:
        parts.append(
            f"<details><summary>다른 학과 공지로 보여 접어둠 ({len(others)}건, 눌러서 확인 가능)</summary>"
            + "<ul class='notice-list'>"
            + "\n".join(render_item(n) for n in others)
            + "</ul></details>"
        )

    return "\n".join(parts)


def build():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    meta = data["meta"]
    sites_html = "\n".join(render_site(s) for s in data["sites"])
    keywords = html.escape(", ".join(meta.get("my_keywords", []))) or "(없음)"

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
<p id="unread-count" class="unread-count"></p>
{sites_html}
<script>{READ_STATE_SCRIPT}</script>
</body>
</html>"""

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(page, encoding="utf-8")
    print(f"빌드 완료 -> {OUT_FILE}")


if __name__ == "__main__":
    build()
