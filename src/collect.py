"""collect.py - 인천대 알림 사이트를 스크래핑해서 data/data.json을 최신 상태로 갱신한다.

GitHub Actions가 매일 이 스크립트를 실행한다 (.github/workflows/update.yml).
로컬에서 직접 실행할 수도 있다: python src/collect.py
"""

import csv
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
SITES_CSV = ROOT / "input" / "sites.csv"
KEYWORDS_TXT = ROOT / "input" / "my_keywords.txt"
DATA_FILE = ROOT / "data" / "data.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
REQUEST_DELAY_SEC = 1.0  # 사이트마다 너무 빠르게 요청하지 않기 위한 딜레이

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
    """인천대 표준 게시판 템플릿(board-table)을 쓰는 게시판을 스크래핑한다."""
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
PARSERS = {
    "inu_standard": scrape_inu_standard,
}


def collect_site(site, my_keywords):
    parser = PARSERS.get(site.get("parser", "").strip())
    if parser is None:
        print(f"  [건너뜀] {site['name']}: 등록된 파서가 없음 ({site.get('parser')})")
        return {"name": site["name"], "url": site["url"], "notices": [], "error": "파서 없음"}

    try:
        raw_notices = parser(site["url"])
    except requests.RequestException as e:
        print(f"  [경고] {site['name']} 요청 실패: {e}")
        return {"name": site["name"], "url": site["url"], "notices": [], "error": str(e)}

    notices = []
    for n in raw_notices:
        relevant, matched_dept = classify_relevance(n["title"], n["writer"], my_keywords)
        notices.append({**n, "relevant": relevant, "matched_dept": matched_dept})

    print(f"  {site['name']}: {len(notices)}건 수집")
    return {"name": site["name"], "url": site["url"], "notices": notices, "error": None}


def main():
    now = datetime.now(KST)
    print(f"[collect.py] 실행: {now:%Y-%m-%d %H:%M} KST")

    sites = load_sites()
    if not sites:
        print(f"사이트 목록이 비어 있습니다. {SITES_CSV}를 채워주세요.")
        return

    my_keywords = load_my_keywords()

    results = []
    for i, site in enumerate(sites):
        if i > 0:
            time.sleep(REQUEST_DELAY_SEC)
        results.append(collect_site(site, my_keywords))

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
