"""import_starinu.py - 직접 저장한 스타인유 소그룹 공지사항 게시판 화면(HTML)에서 공지를 읽어 data/data.json에 넣는다.

스타인유(starinu.inu.ac.kr)는 포털 로그인을 해야만 글이 보여서 GitHub Actions(collect.py)가
직접 긁어올 수 없다. 그래서 사람이 로그인한 브라우저에서 게시판 첫 페이지를 Ctrl+S로
input/starinu/ 폴더에 저장하면, 이 스크립트가 그 파일을 읽어서 공지를 추가한다.

- 처음 넣을 때(이 게시판 글이 아직 하나도 없을 때): 최근 글 FIRST_IMPORT_COUNT개를 넣는다.
- 그 다음부터: 이미 넣은 글(링크로 구분)은 건너뛰고 새로 올라온 글만 추가한다.

공지는 shortcut_reminders.csv의 바로가기 카드와 같은 이름의 사이트 아래에 넣는다.
collect.py의 collect_reminders가 같은 이름의 기존 공지를 그대로 보존하므로, 매일 자동
수집이 돌아도 여기서 넣은 글이 지워지지 않는다.

실행: python src/import_starinu.py  (그 다음 python src/build_site.py)
"""

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from collect import DATA_FILE, ROOT, classify_relevance, load_my_keywords

SITE_NAME = "스타인유 소그룹 공지사항"  # shortcut_reminders.csv의 name과 반드시 같아야 함
BOARD_URL = "https://starinu.inu.ac.kr/ptfol/comm/board/9527a0c7675872f1058cf3435aa8c4df/index.do"
VIEW_URL = BOARD_URL.replace("index.do", "view.do")
SAVE_DIR = ROOT / "input" / "starinu"
FIRST_IMPORT_COUNT = 10

# 제목 링크는 실제 주소 대신 onclick="global.write('1005236', './view.do');"로 글을 연다.
# 이 글 번호(dataSeq)를 view.do?dataSeq=... 로 붙이면 글 주소가 된다 (게시판 폼이 GET 방식).
DATA_SEQ = re.compile(r"global\.write\(\s*'(\d+)'")


def latest_saved_page():
    pages = sorted(SAVE_DIR.glob("*.htm*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return pages[0] if pages else None


def parse_board(html_text):
    """저장한 게시판 화면에서 공지 목록을 읽는다. 상단 고정("공지") 글도 포함된다."""
    soup = BeautifulSoup(html_text, "html.parser")
    notices = []
    for row in soup.select("table.t_list tbody tr"):
        link_tag = row.select_one("td.title a")
        if link_tag is None:
            continue
        m = DATA_SEQ.search(link_tag.get("onclick", ""))
        if not m:
            continue
        writer_tag = row.select_one("td[data-th='작성자']")
        date_tag = row.select_one("td[data-th='작성일']")
        notices.append(
            {
                "title": link_tag.get_text(strip=True),
                "link": f"{VIEW_URL}?dataSeq={m.group(1)}",
                "writer": writer_tag.get_text(strip=True) if writer_tag else "",
                "date": date_tag.get_text(strip=True) if date_tag else "",
            }
        )
    return notices


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    page = latest_saved_page()
    if page is None:
        print(f"저장된 게시판 화면이 없습니다. 로그인한 브라우저에서 Ctrl+S로 {SAVE_DIR}에 저장해주세요.")
        return
    rows = parse_board(page.read_text(encoding="utf-8"))
    if not rows:
        print(f"[주의] {page.name}에서 공지를 못 찾았습니다. 로그인 화면이 저장된 건 아닌지 확인해주세요.")
        return

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    site = next((s for s in data["sites"] if s["name"] == SITE_NAME), None)
    if site is None:
        site = {"name": SITE_NAME, "url": BOARD_URL, "group": "인천대", "notices": [], "error": None}
        data["sites"].append(site)

    # 바로가기 카드(링크에 remind=가 붙은 것)는 실제 글이 아니므로 "처음인지" 판단에서 뺀다.
    imported = [n for n in site["notices"] if "remind=" not in n["link"]]
    known_links = {n["link"] for n in site["notices"]}
    if imported:
        new_rows = [r for r in rows if r["link"] not in known_links]
    else:
        new_rows = sorted(rows, key=lambda r: r["date"], reverse=True)[:FIRST_IMPORT_COUNT]

    if not new_rows:
        print(f"{SITE_NAME}: 새 공지 없음 ({page.name})")
        return

    my_keywords = load_my_keywords()
    for r in new_rows:
        r["relevant"], r["matched_dept"] = classify_relevance(r["title"], r["writer"], my_keywords)
    site["notices"] = new_rows + site["notices"]

    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{SITE_NAME}: 새 공지 {len(new_rows)}건 추가 ({page.name})")
    for r in new_rows:
        print(f"  {r['date']}  {r['title']}")


if __name__ == "__main__":
    main()
