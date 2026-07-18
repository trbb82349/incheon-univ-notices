"""collect.py - 인천대 알림 사이트를 스크래핑해서 data/data.json을 최신 상태로 갱신한다.

동작 방식:
- 사이트를 처음 추가했을 때(그 사이트 기록이 아예 없을 때): 게시판에서 가장 최근 날짜에 올라온
  공지를 전부 가져온다 (페이지에 걸쳐 있으면 여러 페이지를 넘겨서라도 그 날짜 것은 다 가져옴).
- 이후 업데이트할 때: 이전에 이미 저장해둔 공지는 그대로 두고, 그 이후 새로 올라온 공지만
  추가한다. 이미 저장된 글(링크로 구분)을 만나면 그 뒤로는 다 예전 글이므로 페이지 넘기기를 멈춘다.

GitHub Actions가 매일 이 스크립트를 실행한다 (.github/workflows/update.yml).
로컬에서 직접 실행할 수도 있다: python src/collect.py
"""

import csv
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
SITES_CSV = ROOT / "input" / "sites.csv"
KEYWORDS_TXT = ROOT / "input" / "my_keywords.txt"
DATA_FILE = ROOT / "data" / "data.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
REQUEST_DELAY_SEC = 1.0  # 요청 사이마다 너무 빠르게 보내지 않기 위한 딜레이
MAX_PAGES = 15  # 새 글/최근 글을 찾으려고 페이지를 넘길 때의 안전 상한
MAX_STORED_PER_SITE = 300  # 사이트 하나당 보관하는 공지 최대 개수 (계속 쌓이기만 하는 것 방지)

# 공지 제목/작성부서에서 "OO학과", "OO학부", "OO전공" 형태의 학과 이름을 찾는 패턴
DEPT_PATTERN = re.compile(r"[가-힣]+(?:학과|학부|전공)")


def load_sites():
    if not SITES_CSV.exists():
        return []
    with SITES_CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_my_keywords():
    if not KEYWORDS_TXT.exists():
        return []
    lines = KEYWORDS_TXT.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def load_existing_data():
    if not DATA_FILE.exists():
        return {}
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {s["name"]: s for s in data.get("sites", [])}


def classify_relevance(title, writer, my_keywords):
    """제목/작성부서에서 다른 학과 이름이 발견되고, 내 키워드와 겹치지 않으면 '관련 없음'으로 본다.
    학과 이름이 아예 없으면(전체 대상 공지로 보이면) '관련 있음'으로 둔다."""
    combined = f"{title} {writer}"
    found = set(DEPT_PATTERN.findall(combined))
    if not found:
        return True, None
    for dept in found:
        if any(kw in dept or dept in kw for kw in my_keywords):
            return True, None
    return False, ", ".join(sorted(found))


def scrape_inu_standard(url):
    """인천대 표준 게시판 템플릿(board-table)을 쓰는 게시판 1페이지를 스크래핑한다."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    notices = []
    for row in soup.select("table.board-table tbody tr"):
        link_tag = row.select_one("td.td-subject a")
        if link_tag is None:
            continue
        title = link_tag.get_text(strip=True)
        title = re.sub(r"(새글|New)$", "", title).strip()
        link = urljoin(url, link_tag["href"])
        writer_tag = row.select_one("td.td-write")
        date_tag = row.select_one("td.td-date")
        notices.append(
            {
                "title": title,
                "link": link,
                "writer": writer_tag.get_text(strip=True) if writer_tag else "",
                "date": date_tag.get_text(strip=True) if date_tag else "",
            }
        )
    return notices


# 사이트별 파서 등록. sites.csv의 parser 칸에 적힌 이름으로 찾는다.
# 새 사이트가 다른 구조를 쓰면 함수를 하나 더 만들어 여기에 등록하면 된다.
# 파서는 "게시판 목록 페이지 URL 1개"를 받아 그 페이지에 있는 공지 목록을 반환한다.
PARSERS = {
    "inu_standard": scrape_inu_standard,
}


def with_page(url, page):
    """URL의 page= 쿼리 값을 바꿔서 다른 페이지 주소를 만든다."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["page"] = str(page)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def fetch_new_notices(fetch_page, base_url, known_links):
    """새로 나온 공지만 가져온다.

    known_links가 비어 있으면(이 사이트를 처음 추가한 경우) 게시판에서 가장 최근 날짜에
    해당하는 글을 전부 가져온다(여러 페이지에 걸쳐 있어도 계속 넘긴다).

    known_links에 이미 글이 있으면(예전에 한 번 이상 수집한 사이트), 이미 알고 있는 글을
    만날 때까지만 페이지를 넘기며 그 앞의(더 최신인) 새 글들을 가져온다.
    """
    is_bootstrap = not known_links
    latest_date = None
    collected = []

    for page in range(1, MAX_PAGES + 1):
        rows = fetch_page(with_page(base_url, page))
        if not rows:
            break

        if is_bootstrap:
            if latest_date is None:
                latest_date = rows[0]["date"]
            matching = [r for r in rows if r["date"] == latest_date]
            collected.extend(matching)
            reached_boundary = len(matching) < len(rows)
        else:
            page_new = []
            reached_boundary = False
            for r in rows:
                if r["link"] in known_links:
                    reached_boundary = True
                    break
                page_new.append(r)
            collected.extend(page_new)

        if reached_boundary:
            break
        if page < MAX_PAGES:
            time.sleep(REQUEST_DELAY_SEC)
    else:
        print(f"  [주의] {MAX_PAGES}페이지까지 전부 새 글이라 더 있을 수 있음 (안전 상한 도달)")

    return collected


def collect_site(site, my_keywords, existing_site):
    parser = PARSERS.get(site.get("parser", "").strip())
    prev_notices = existing_site["notices"] if existing_site else []

    if parser is None:
        print(f"  [건너뜀] {site['name']}: 등록된 파서가 없음 ({site.get('parser')})")
        return {"name": site["name"], "url": site["url"], "notices": prev_notices, "error": "파서 없음"}

    known_links = {n["link"] for n in prev_notices}

    try:
        new_rows = fetch_new_notices(parser, site["url"], known_links)
    except requests.RequestException as e:
        print(f"  [경고] {site['name']} 요청 실패: {e} (기존 데이터 유지)")
        return {"name": site["name"], "url": site["url"], "notices": prev_notices, "error": str(e)}

    if new_rows:
        print(f"  {site['name']}: 새 공지 {len(new_rows)}건 발견")
    else:
        print(f"  {site['name']}: 새 공지 없음")

    # 새 글 + 기존 글을 합치고, 최신 키워드 기준으로 관련 여부를 다시 계산한다.
    merged = new_rows + prev_notices
    notices = []
    for n in merged[:MAX_STORED_PER_SITE]:
        relevant, matched_dept = classify_relevance(n["title"], n["writer"], my_keywords)
        notices.append({**n, "relevant": relevant, "matched_dept": matched_dept})

    return {"name": site["name"], "url": site["url"], "notices": notices, "error": None}


def main():
    now = datetime.now(KST)
    print(f"[collect.py] 실행: {now:%Y-%m-%d %H:%M} KST")

    sites = load_sites()
    if not sites:
        print(f"사이트 목록이 비어 있습니다. {SITES_CSV}를 채워주세요.")
        return

    my_keywords = load_my_keywords()
    existing_by_name = load_existing_data()

    results = []
    for i, site in enumerate(sites):
        if i > 0:
            time.sleep(REQUEST_DELAY_SEC)
        results.append(collect_site(site, my_keywords, existing_by_name.get(site["name"])))

    data = {
        "meta": {
            "last_updated": now.strftime("%Y-%m-%d %H:%M"),
            "my_keywords": my_keywords,
        },
        "sites": results,
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료 -> {DATA_FILE}")


if __name__ == "__main__":
    main()
