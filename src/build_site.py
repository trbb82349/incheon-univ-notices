"""build_site.py - data/data.json을 읽어 docs/index.html을 만든다.

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
.update-bar { color: #666; font-size: 13px; margin-bottom: 24px; }
h2 { border-bottom: 2px solid #222; padding-bottom: 4px; margin-top: 32px; }
h3 { font-size: 15px; color: #444; margin-top: 20px; }
ul { list-style: none; padding: 0; }
li { padding: 8px 0; border-bottom: 1px solid #eee; font-size: 14px; }
li a { color: #1a4fb4; text-decoration: none; }
li a:hover { text-decoration: underline; }
.meta { color: #888; font-size: 12px; }
details summary { cursor: pointer; color: #666; font-size: 14px; margin-top: 12px; }
.error { color: #b00020; font-size: 13px; }
"""


def render_item(n):
    title = html.escape(n["title"])
    link = html.escape(n["link"])
    writer = html.escape(n["writer"])
    date = html.escape(n["date"])
    extra = f" <span class='meta'>- {html.escape(n['matched_dept'])}</span>" if n.get("matched_dept") else ""
    return f"<li><a href='{link}' target='_blank' rel='noopener'>{title}</a> <span class='meta'>{writer} ({date})</span>{extra}</li>"


def render_site(site):
    parts = [f"<h2>{html.escape(site['name'])}</h2>"]

    if site.get("error"):
        parts.append(f"<p class='error'>수집 실패: {html.escape(site['error'])}</p>")
        return "\n".join(parts)

    notices = site["notices"]
    if not notices:
        parts.append("<p>오늘 새로 올라온 공지가 없습니다.</p>")
        return "\n".join(parts)

    relevant = [n for n in notices if n["relevant"]]
    others = [n for n in notices if not n["relevant"]]

    parts.append("<h3>나와 관련된 공지</h3>")
    if relevant:
        parts.append("<ul>" + "\n".join(render_item(n) for n in relevant) + "</ul>")
    else:
        parts.append("<p>없음</p>")

    if others:
        parts.append(
            f"<details><summary>다른 학과 공지로 보여 접어둠 ({len(others)}건, 눌러서 확인 가능)</summary>"
            + "<ul>"
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
<p class="update-bar">{html.escape(meta.get('today', ''))} 오늘 올라온 공지 · 마지막 갱신: {html.escape(meta.get('last_updated', ''))} KST · 내 학과 키워드: {keywords}</p>
{sites_html}
</body>
</html>"""

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(page, encoding="utf-8")
    print(f"빌드 완료 -> {OUT_FILE}")


if __name__ == "__main__":
    build()
