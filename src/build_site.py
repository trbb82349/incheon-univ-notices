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
@import url('https://fonts.googleapis.com/css2?family=Jua&display=swap');

* { box-sizing: border-box; }

:root {
  --sky: #86c2dc;
  --sky-dark: #4f7f9c;
  --sky-pale: #eaf3f7;
  --sky-mid: #d6e7ee;
  --pink: #dda6b4;
  --pink-pale: #f4e7ea;
  --gold: #ddc07d;
  --gold-pale: #f4eeda;
  --green: #8db892;
  --green-pale: #e7f0e7;
  --ink: #3d5261;
  --ink-soft: #7c8f9a;
  --title: #3b3b3b;
  --lavender: #9a8fc2;
  --lavender-pale: #ece8f5;
}

body {
  font-family: -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  margin: 0;
  padding: 0;
  color: var(--ink);
  background: linear-gradient(180deg, #eaf7ff 0%, #f7fcff 200px, #f7fcff 100%);
  min-height: 100vh;
}

.app-shell { max-width: 560px; margin: 0 auto; padding: 20px 16px 48px; }

.hero {
  text-align: center;
  padding: 22px 16px 18px;
  margin-bottom: 18px;
  background: linear-gradient(135deg, var(--sky) 0%, #a9d0e0 100%);
  border-radius: 22px;
  box-shadow: 0 8px 20px rgba(134, 194, 220, 0.35);
  color: #fff;
}
h1 { font-family: 'Jua', sans-serif; font-weight: 400; font-size: 24px; margin: 0 0 4px; letter-spacing: -0.5px; }
.tagline { font-size: 13px; margin: 0; opacity: 0.95; }
.update-bar {
  display: inline-block;
  margin-top: 10px;
  font-size: 11px;
  background: rgba(255,255,255,0.25);
  padding: 4px 12px;
  border-radius: 999px;
}

.tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; justify-content: center; }
.tab-btn {
  font-family: 'Jua', sans-serif;
  font-weight: 400;
  font-size: 13px;
  padding: 9px 14px;
  border: 2px solid var(--sky-mid);
  border-radius: 999px;
  background: #fff;
  cursor: pointer;
  color: var(--sky-dark);
  transition: transform 0.1s ease, background 0.15s ease;
}
.tab-btn:active { transform: scale(0.96); }
.tab-btn.active { background: linear-gradient(135deg, var(--sky) 0%, var(--sky-dark) 100%); color: #fff; border-color: transparent; box-shadow: 0 4px 10px rgba(79, 127, 156, 0.35); }
.tab-btn .count { font-size: 11px; opacity: 0.85; }

.notice-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
.notice-item {
  background: #fff;
  border-radius: 16px;
  padding: 14px 16px;
  box-shadow: 0 3px 10px rgba(134, 194, 220, 0.16);
  border: 1px solid var(--sky-pale);
  touch-action: pan-y;
  user-select: none;
}
.notice-item.tab-hidden { display: none; }
.notice-item.is-read { background: #f6f9fb; opacity: 0.72; }
.notice-item.is-read .notice-link { text-decoration: line-through; }

.notice-link { display: block; color: var(--title); text-decoration: none; font-weight: 600; font-size: 15px; line-height: 1.4; margin-bottom: 6px; }
.notice-link:active { opacity: 0.7; }

.meta { display: inline-block; color: var(--ink-soft); font-size: 11.5px; background: var(--sky-pale); padding: 2px 9px; border-radius: 999px; margin-bottom: 8px; }
.source-tag { display: inline-block; color: #5d5285; font-size: 11.5px; background: var(--lavender-pale); padding: 2px 9px; border-radius: 999px; margin-left: 4px; margin-bottom: 8px; }
.dept-tag { display: inline-block; color: #a3607a; font-size: 11.5px; background: var(--pink-pale); padding: 2px 9px; border-radius: 999px; margin-left: 4px; margin-bottom: 8px; }

.btn-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.notice-item button {
  font-size: 12px;
  padding: 7px 12px;
  border: none;
  border-radius: 999px;
  cursor: pointer;
  font-weight: 600;
  transition: transform 0.1s ease;
}
.notice-item button:active { transform: scale(0.94); }
.mark-read-btn { background: var(--green-pale); color: #4d7355; }
.star-btn { background: var(--gold-pale); color: #7a6640; }
.star-btn.is-active { background: var(--gold); color: #5c4a28; }
.mark-relevant-btn { background: var(--sky-pale); color: var(--sky-dark); }

.empty-msg { text-align: center; color: var(--ink-soft); font-size: 14px; padding: 40px 20px; background: #fff; border-radius: 16px; border: 1px dashed var(--sky-mid); }
.error { color: #c0392b; font-size: 13px; background: #fdecea; padding: 10px 14px; border-radius: 12px; }

@media (min-width: 620px) {
  body { padding: 24px 0; }
  .app-shell { background: #fff; border-radius: 28px; box-shadow: 0 12px 40px rgba(134, 194, 220, 0.25); padding: 28px 28px 40px; }
}

@media (max-width: 360px) {
  .app-shell { padding: 14px 10px 40px; }
  .notice-item { padding: 12px 13px; }
  h1 { font-size: 21px; }
}
"""

TAB_LABELS = [
    ("unread", "📩 안 읽은 공지"),
    ("read", "✅ 읽은 공지"),
    ("starred", "⭐ 주요 공지"),
    ("other", "📚 다른 학과"),
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

  function toggleRead(link) {
    if (readSet.has(link)) readSet.delete(link); else readSet.add(link);
    saveSet(READ_KEY, readSet);
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
      readBtn.textContent = isRead ? '↩️ 안읽음으로' : '✅ 읽음으로 표시';
    }
    if (starBtn) {
      starBtn.style.display = relevant ? '' : 'none';
      starBtn.classList.toggle('is-active', isStar);
      starBtn.textContent = isStar ? '★ 즐겨찾기 해제' : '☆ 즐겨찾기';
    }
    if (relBtn) {
      // 원래(서버 기준) 다른 학과 공지였던 것만 이 버튼을 보여준다.
      // 관련 공지로 표시한 뒤에도 계속 보여야 다시 되돌릴 수 있다.
      relBtn.style.display = serverRelevant ? 'none' : '';
      relBtn.textContent = overrideSet.has(link) ? '↩️ 다른 학과로' : '💙 관련 공지예요';
    }
  }

  function refresh() {
    var counts = { unread: 0, read: 0, starred: 0, other: 0 };
    var items = document.querySelectorAll('.notice-item');

    // "읽은 공지" 탭만 최근에 읽은 순으로 보여준다. readSet은 읽음으로 표시한 순서대로
    // 쌓이는 자바스크립트 Set이라(먼저 읽은 게 앞), 뒤집으면 최근에 읽은 것부터 나온다.
    // .notice-list가 flex라서, DOM 순서는 그대로 두고 order 값만 바꿔서 화면 순서를 조정한다.
    var readOrderIndex = null;
    if (activeTab === 'read') {
      readOrderIndex = {};
      Array.from(readSet).reverse().forEach(function (l, i) { readOrderIndex[l] = i; });
    }

    items.forEach(function (li) {
      Object.keys(counts).forEach(function (tab) {
        if (matchesTab(li, tab)) counts[tab]++;
      });
      li.classList.toggle('tab-hidden', !matchesTab(li, activeTab));

      if (readOrderIndex) {
        var link = li.getAttribute('data-link');
        li.style.order = link in readOrderIndex ? readOrderIndex[link] : '';
      } else {
        li.style.order = ''; // 다른 탭에서는 원래대로 최신 날짜순(원래 화면에 적힌 순서)
      }
    });

    // 일부 모바일 브라우저는 order 값만 바꾸면 화면을 바로 다시 안 그리는 경우가 있어서,
    // 강제로 한 번 더 계산하게 만든다(이미 계산해둔 값을 다시 읽기만 해도 강제로 다시 그려진다).
    void document.body.offsetHeight;

    document.querySelectorAll('.tab-btn').forEach(function (btn) {
      var tab = btn.getAttribute('data-tab');
      btn.classList.toggle('active', tab === activeTab);
      var countEl = btn.querySelector('.count');
      if (countEl) countEl.textContent = ' (' + counts[tab] + ')';
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
        toggleRead(link);
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

    // 카드를 좌우로 밀면(스와이프) 읽음으로 표시한다.
    // 제목 글자(링크) 위가 카드에서 가장 넓은 면적을 차지하기 때문에(특히 휴대폰에서),
    // 스와이프 시작을 링크 위에서도 허용해야 한다. 대신 실제로 많이 끌었을 때는(wasDragged)
    // 링크의 클릭(=새 창 열기)을 막아서, 스와이프와 "눌러서 열기"가 서로 안 부딪히게 한다.
    var SWIPE_THRESHOLD = 80;
    var DRAG_MOVE_THRESHOLD = 10; // 이만큼 넘게 움직이면 "탭"이 아니라 "끌기"로 본다
    var swipeStartX = null;
    var swipeStartY = null;
    var swipePointerId = null;
    var swipeDX = 0;
    var wasDragged = false;

    var a = li.querySelector('.notice-link');
    if (a) {
      a.addEventListener('click', function (e) {
        if (wasDragged) {
          e.preventDefault();
          return;
        }
        if (isRelevant(li) && !readSet.has(link)) {
          toggleRead(link);
          applyItemState(li);
          refresh();
        }
      });
    }

    li.addEventListener('pointerdown', function (e) {
      if (!isRelevant(li)) return; // 다른 학과 공지는 읽음 기능이 없으니 스와이프도 안 함
      if (e.target.closest('button')) return; // 버튼은 그대로 누르게 둔다
      swipePointerId = e.pointerId;
      swipeStartX = e.clientX;
      swipeStartY = e.clientY;
      swipeDX = 0;
      wasDragged = false;
      li.style.transition = 'none';
    });

    li.addEventListener('pointermove', function (e) {
      if (swipeStartX === null || e.pointerId !== swipePointerId) return;
      swipeDX = e.clientX - swipeStartX;
      var dy = e.clientY - swipeStartY;
      // 위아래로 더 많이 움직였으면(스크롤 의도) 좌우 스와이프로 보지 않는다.
      if (Math.abs(dy) > Math.abs(swipeDX)) return;
      if (Math.abs(swipeDX) > DRAG_MOVE_THRESHOLD) wasDragged = true;
      li.style.transform = 'translateX(' + swipeDX + 'px)';
      li.style.opacity = String(Math.max(1 - Math.abs(swipeDX) / 300, 0.4));
    });

    function endSwipe(e) {
      if (swipeStartX === null || e.pointerId !== swipePointerId) return;
      var dx = swipeDX;
      swipeStartX = null;
      swipePointerId = null;
      swipeDX = 0;
      li.style.transition = 'transform 0.25s ease, opacity 0.25s ease';

      if (Math.abs(dx) >= SWIPE_THRESHOLD) {
        var flyTo = dx > 0 ? 500 : -500;
        li.style.transform = 'translateX(' + flyTo + 'px)';
        li.style.opacity = '0';
        setTimeout(function () {
          toggleRead(link);
          applyItemState(li);
          li.style.transition = 'none';
          li.style.transform = '';
          li.style.opacity = '';
          refresh();
        }, 220);
      } else {
        li.style.transform = '';
        li.style.opacity = '';
      }
    }

    li.addEventListener('pointerup', endSwipe);
    li.addEventListener('pointercancel', endSwipe);
  });

  refresh();
})();
"""


def render_item(n):
    title = html.escape(n["title"])
    link = html.escape(n["link"])
    writer = html.escape(n["writer"])
    date = html.escape(n["date"])
    source = html.escape(n["site"])
    relevant = "true" if n["relevant"] else "false"
    dept_tag = f"<span class='dept-tag'>🏷️ {html.escape(n['matched_dept'])}</span>" if n.get("matched_dept") else ""
    return (
        f"<li class='notice-item' data-link='{link}' data-relevant='{relevant}'>"
        f"<a href='{link}' target='_blank' rel='noopener' class='notice-link'>{title}</a>"
        f"<span class='meta'>{writer} · {date}</span>"
        f"<span class='source-tag'>🏫 {source}</span>{dept_tag}"
        f"<div class='btn-row'>"
        f"<button type='button' class='mark-read-btn'>✅ 읽음으로 표시</button>"
        f"<button type='button' class='star-btn'>☆ 즐겨찾기</button>"
        f"<button type='button' class='mark-relevant-btn'>💙 관련 공지예요</button>"
        f"</div>"
        f"</li>"
    )


def build():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    meta = data["meta"]
    keywords = html.escape(", ".join(meta.get("my_keywords", []))) or "(없음)"

    error_parts = []
    all_notices = []
    for site in data["sites"]:
        if site.get("error"):
            error_parts.append(f"<p class='error'>{html.escape(site['name'])} 수집 실패: {html.escape(site['error'])}</p>")
            continue
        for n in site["notices"]:
            all_notices.append({**n, "site": site["name"]})

    # 사이트 구분 없이 하나로 합치고, 날짜(YYYY.MM.DD) 최신순으로 정렬한다.
    all_notices.sort(key=lambda n: n["date"], reverse=True)

    errors_html = "\n".join(error_parts)
    if all_notices:
        notices_html = "<ul class='notice-list'>" + "\n".join(render_item(n) for n in all_notices) + "</ul>"
    else:
        notices_html = "<p>아직 수집된 공지가 없습니다.</p>"

    tabs_html = "\n".join(
        f"<button type='button' class='tab-btn{' active' if tab_id == 'unread' else ''}' data-tab='{tab_id}'>"
        f"{html.escape(label)}<span class='count'></span></button>"
        for tab_id, label in TAB_LABELS
    )

    favicon = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>💙</text></svg>"

    page = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>인천대 알림 모음</title>
<link rel="icon" href="{favicon}">
<style>{STYLE}</style>
</head>
<body>
<div class="app-shell">
<div class="hero">
<h1>💙 인천대 알림 모음</h1>
<p class="tagline">매일 아침 조용히 챙겨주는 공지 비서 ✨</p>
<span class="update-bar">🕐 {html.escape(meta.get('last_updated', ''))} 기준 · {keywords}</span>
</div>
<div class="tabs">{tabs_html}</div>
{errors_html}
<p id="empty-msg" class="empty-msg">🎉 이 탭에는 표시할 공지가 없어요!</p>
{notices_html}
</div>
<script>{READ_STATE_SCRIPT}</script>
</body>
</html>"""

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(page, encoding="utf-8")
    print(f"빌드 완료 -> {OUT_FILE}")


if __name__ == "__main__":
    build()
