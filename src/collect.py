"""collect.py - 인천대 알림 사이트를 스크래핑해서 data/data.json을 최신 상태로 갱신한다.

동작 방식:
- 사이트를 처음 추가했을 때(그 사이트 기록이 아예 없을 때): 최근에 올라온 글은 물론,
  제목에 "~7/24", "7월 20일부터 7월 31일까지" 같은 신청/행사 기간이 적혀 있고
  그 기간이 오늘이거나 오늘 이후까지 걸쳐 있는 글이면(아직 시작 전인 공지 포함,
  마감일이 이미 지난 것만 제외) 며칠 전에 올라온 글이라도 다 찾아서 가져온다.
  (페이지를 계속 넘기다가, 어느 페이지에 더 이상 해당하는 글이 하나도 없으면 멈춘다.)
- 이후 업데이트할 때: 이전에 이미 저장해둔 공지는 그대로 두고, 그 이후 새로 올라온 공지만
  추가한다. 이미 저장된 글(링크로 구분)을 만나면 그 뒤로는 다 예전 글이므로 페이지 넘기기를 멈춘다.

GitHub Actions가 매일 이 스크립트를 실행한다 (.github/workflows/update.yml).
로컬에서 직접 실행할 수도 있다: python src/collect.py
"""

import csv
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
SITES_CSV = ROOT / "input" / "sites.csv"
KEYWORDS_TXT = ROOT / "input" / "my_keywords.txt"
REMINDERS_CSV = ROOT / "input" / "everytime_reminders.csv"
DATA_FILE = ROOT / "data" / "data.json"

WEEKDAY_KO = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
REQUEST_DELAY_SEC = 1.0  # 요청 사이마다 너무 빠르게 보내지 않기 위한 딜레이
MAX_INCREMENTAL_PAGES = 15  # 업데이트할 때 새 글을 찾으려고 페이지를 넘길 때의 안전 상한
MAX_BOOTSTRAP_PAGES = 30  # 사이트를 처음 추가할 때 기간이 겹치는 글을 찾으려고 넘길 때의 안전 상한
RECENT_DAYS = 3  # 이 기간 안에 올라온 글은 제목에 기간이 없어도 일단 "최근 글"로 포함
MAX_STORED_PER_SITE = 300  # 사이트 하나당 보관하는 공지 최대 개수 (계속 쌓이기만 하는 것 방지)

# 공지 제목/작성부서에서 "OO학과", "OO학부", "OO전공" 형태의 학과 이름을 찾는 패턴
DEPT_PATTERN = re.compile(r"[가-힣]+(?:학과|학부|전공)")

# 제목에서 "월/일" 하나를 찾는 조각: 7/20, 7.20, 7월 20일, 7/20(월) 모두 허용
# (뒤에 붙는 "(월)" 같은 요일 표시는 건너뛴다 - 안 그러면 "7/20(월) ~ 8/21(금)"에서
#  시작일 7/20을 놓치고 "~8/21"만 마감일로 잘못 읽어서, 아직 시작 전인 기간을
#  이미 시작한 것으로 착각하는 문제가 있었다.)
_MD = r"(\d{1,2})\s*(?:[./]|월)\s*(\d{1,2})\s*일?(?:\([가-힣]\))?"
PERIOD_RANGE_WORDS = re.compile(rf"{_MD}\s*부터\s*{_MD}\s*까지")
PERIOD_RANGE_TILDE = re.compile(rf"{_MD}\s*[~\-∼～]\s*{_MD}")
PERIOD_DEADLINE_TILDE = re.compile(rf"[~∼～]\s*{_MD}")
PERIOD_DEADLINE_WORD = re.compile(rf"{_MD}\s*까지")


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


def load_reminders():
    """월/목처럼 정해진 요일마다 '이 게시판 확인해보세요' 카드를 만들 대상 목록을 읽는다.
    실제 글을 긁어오는 게 아니라, 그 사이트로 가는 바로가기 알림이다(로그인이 필요한
    에브리타임 같은 곳을 위한 것)."""
    if not REMINDERS_CSV.exists():
        return []
    with REMINDERS_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    reminders = []
    for row in rows:
        weekdays = {
            WEEKDAY_KO[w.strip()] for w in row["weekdays"].split(",") if w.strip() in WEEKDAY_KO
        }
        reminders.append({"name": row["name"].strip(), "url": row["url"].strip(), "weekdays": weekdays})
    return reminders


def build_reminder_notice(reminder, today):
    """오늘 날짜를 링크에 붙여서, 매번 "새 글"처럼 인식되도록 만든다
    (똑같은 링크를 계속 쓰면 한 번 읽음 처리한 뒤로는 다시 안 올라오기 때문).
    실제로 눌렀을 때는 뒤에 붙은 물음표 이후 부분은 무시되고 원래 게시판으로 이동한다."""
    return {
        "title": f"{reminder['name']} 보기",
        "link": f"{reminder['url']}?remind={today.isoformat()}",
        "writer": "정기 알림",
        "date": today.strftime("%Y.%m.%d"),
        "relevant": True,
        "matched_dept": None,
    }


def collect_reminders(reminders, existing_by_name, today):
    """요일에 맞는 사이트마다 오늘 알림 카드가 필요하면 추가하고, 해당 안 되는 날에도
    이전에 만들어둔 카드들은 그대로 보존한다."""
    today_weekday = today.weekday()
    results = []
    for reminder in reminders:
        existing_site = existing_by_name.get(reminder["name"])
        notices = existing_site["notices"] if existing_site else []
        if today_weekday in reminder["weekdays"]:
            notice = build_reminder_notice(reminder, today)
            if not any(n["link"] == notice["link"] for n in notices):
                notices = [notice] + notices
                print(f"  {reminder['name']}: 오늘 알림 카드 추가")
        results.append(
            {
                "name": reminder["name"],
                "url": reminder["url"],
                "notices": notices[:MAX_STORED_PER_SITE],
                "error": None,
            }
        )
    return results


def load_existing_data():
    if not DATA_FILE.exists():
        return {}
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {s["name"]: s for s in data.get("sites", [])}


def _valid_md(m, d):
    return 1 <= m <= 12 and 1 <= d <= 31


def parse_title_period(title):
    """제목에서 "~7/24", "7월 20일부터 7월 31일까지", "7/20~7/31" 같은 신청/행사 기간을 찾는다.
    (시작 (월,일) 또는 None, 끝 (월,일) 또는 None)을 돌려준다. 못 찾으면 (None, None)."""
    m = PERIOD_RANGE_WORDS.search(title)
    if m:
        m1, d1, m2, d2 = map(int, m.groups())
        if _valid_md(m1, d1) and _valid_md(m2, d2):
            return (m1, d1), (m2, d2)

    m = PERIOD_RANGE_TILDE.search(title)
    if m:
        m1, d1, m2, d2 = map(int, m.groups())
        if _valid_md(m1, d1) and _valid_md(m2, d2):
            return (m1, d1), (m2, d2)

    m = PERIOD_DEADLINE_TILDE.search(title)
    if m:
        m2, d2 = map(int, m.groups())
        if _valid_md(m2, d2):
            return None, (m2, d2)

    m = PERIOD_DEADLINE_WORD.search(title)
    if m:
        m2, d2 = map(int, m.groups())
        if _valid_md(m2, d2):
            return None, (m2, d2)

    return None, None


def _resolve_date(md, year, posted):
    """(월,일)을 실제 date로 만든다. 연말/연초를 넘나드는 경우 posted 날짜와 너무 동떨어지면
    다음 해로 넘겨서 보정한다 (예: 12월에 올라온 글의 "~1/5"는 다음 해 1월 5일)."""
    if md is None:
        return None
    m, d = md
    try:
        result = date(year, m, d)
    except ValueError:
        return None
    if result < posted - timedelta(days=180):
        try:
            result = date(year + 1, m, d)
        except ValueError:
            return None
    return result


def period_still_relevant(title, posted, today):
    """제목에 적힌 기간이 오늘이거나 오늘 이후까지 걸쳐 있으면 True를 돌려준다.
    (아직 시작 전인 "다음 주부터 접수" 같은 공지도 포함 — 오늘 이후에 해당되는 공지이므로.)
    마감일이 이미 지난 게 확실한 경우에만 False. 제목에서 기간을 아예 못 찾았으면 None."""
    start_md, end_md = parse_title_period(title)
    if start_md is None and end_md is None:
        return None
    end = _resolve_date(end_md, posted.year, posted)
    if end and today > end:
        return False  # 마감일이 이미 지났음
    return True  # 아직 진행 중이거나, 시작 전이거나(=오늘 이후에 해당), 마감일이 안 적혀 있음


def is_bootstrap_relevant(row, today):
    """사이트를 처음 추가할 때, 이 글을 초기 목록에 포함할지 정한다.

    "최근 글"이거나 "제목에 적힌 기간이 오늘이거나 오늘 이후까지 걸쳐 있는 글"이면
    포함한다(아직 시작 전인 공지도 포함 — 오늘 이후에 해당되니까). 글이 며칠 전
    것인지는 상관하지 않는다 — 학과 홈페이지처럼 상단에 고정해두고 학기 내내
    걸어두는 공지(예: "~12/31까지")는 올라온 지 몇 달이 지났어도 지금도 유효할
    수 있기 때문이다. (제목에 아무 기간도 안 적혀 있는 오래된 글은
    period_still_relevant가 None을 돌려주므로 자연스럽게 제외된다.)"""
    try:
        posted = datetime.strptime(row["date"], "%Y.%m.%d").date()
    except ValueError:
        return True  # 날짜 형식을 못 읽으면 일단 안전하게 포함

    if (today - posted).days <= RECENT_DAYS:
        return True  # 최근 며칠 안에 올라온 글은 기간 언급이 없어도 포함

    return period_still_relevant(row["title"], posted, today) is True


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


def scrape_inu_js_link(url):
    """인천대 게시판 템플릿의 변형: 제목 링크가 실제 주소(href) 대신
    data-site-id / data-fnct-no / data-bbs-artcl-seq 속성 + 자바스크립트로 이동한다
    (예: 데이터과학과 홈페이지). 그 속성들을 조합해서 실제 글 주소를 직접 만든다."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"

    notices = []
    for row in soup.select("table.board-table tbody tr"):
        link_tag = row.select_one("td.td-subject a.js-view-artcl")
        if link_tag is None:
            continue
        site_id = link_tag.get("data-site-id", "")
        fnct_no = link_tag.get("data-fnct-no", "")
        artcl_seq = link_tag.get("data-bbs-artcl-seq", "")
        if not (site_id and fnct_no and artcl_seq):
            continue
        title_tag = link_tag.select_one("strong")
        title = (title_tag or link_tag).get_text(strip=True)
        link = f"{origin}/bbs/{site_id}/{fnct_no}/{artcl_seq}/artclView"
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


LIB_PAGE_SIZE = 10


def scrape_lib_pyxis(url):
    """학산도서관(lib.inu.ac.kr) 공지사항: 화면은 자바스크립트(Angular)로 그려져서
    requests로는 빈 껍데기만 보이지만, 뒤에서 부르는 JSON API(pyxis-api)를 직접
    호출하면 진짜 데이터를 그대로 받을 수 있다. sites.csv의 URL에 있는 "page="
    값을 이 API가 쓰는 offset(=(page-1)*10)으로 바꿔서 요청한다."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    page = int(query.get("page", "1") or "1")
    offset = (page - 1) * LIB_PAGE_SIZE
    origin = f"{parts.scheme}://{parts.netloc}"
    api_url = (
        f"{origin}/pyxis-api/1/bulletin-boards/1/bulletins"
        f"?offset={offset}&max={LIB_PAGE_SIZE}&nameOption=part&isSeq=false&onlyWriter=false"
    )
    resp = requests.get(api_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    items = resp.json().get("data", {}).get("list", [])

    notices = []
    for item in items:
        date_created = item.get("dateCreated", "")  # "2026-07-16 13:42:20"
        date = date_created[:10].replace("-", ".")
        notices.append(
            {
                "title": item.get("title", ""),
                "link": f"{origin}/library-guide/news/notice/{item['id']}",
                "writer": item.get("writer", ""),
                "date": date,
            }
        )
    return notices


# 사이트별 파서 등록. sites.csv의 parser 칸에 적힌 이름으로 찾는다.
# 새 사이트가 다른 구조를 쓰면 함수를 하나 더 만들어 여기에 등록하면 된다.
# 파서는 "게시판 목록 페이지 URL 1개"를 받아 그 페이지에 있는 공지 목록을 반환한다.
PARSERS = {
    "inu_standard": scrape_inu_standard,
    "inu_js_link": scrape_inu_js_link,
    "inu_lib_pyxis": scrape_lib_pyxis,
}


def with_page(url, page):
    """URL의 page= 쿼리 값을 바꿔서 다른 페이지 주소를 만든다."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["page"] = str(page)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def bootstrap_notices(fetch_page, base_url, today):
    """사이트를 처음 추가할 때: 최근 글 + 제목의 신청/행사 기간에 오늘이 포함되는 글을
    페이지를 넘겨가며 찾는다. 어느 페이지에 새로 찾은 글이 하나도 없으면 그 뒤는 안 본다.

    일부 게시판은 "상단 고정(공지)" 글이 모든 페이지 맨 위에 똑같이 반복해서 나온다.
    그런 글을 페이지마다 중복으로 담지 않도록, 이번 실행에서 이미 담은 링크는 건너뛴다."""
    collected = []
    seen_links = set()
    for page in range(1, MAX_BOOTSTRAP_PAGES + 1):
        rows = fetch_page(with_page(base_url, page))
        if not rows:
            break
        matches = []
        for r in rows:
            if r["link"] in seen_links:
                continue  # 상단 고정 글 등, 이미 이번 실행에서 담은 글
            if is_bootstrap_relevant(r, today):
                seen_links.add(r["link"])
                matches.append(r)
        collected.extend(matches)
        if not matches:
            break
        if page < MAX_BOOTSTRAP_PAGES:
            time.sleep(REQUEST_DELAY_SEC)
    else:
        print(f"  [주의] {MAX_BOOTSTRAP_PAGES}페이지까지 계속 해당 글이 있어서 안전 상한 도달")
    return collected


def fetch_incremental_notices(fetch_page, base_url, known_links):
    """업데이트할 때: 새로 나온 글만 찾아서 가져온다. 한 페이지 안에 이미 아는 글이
    하나라도 섞여 있으면 그 페이지가 "새 글과 예전 글의 경계"라고 보고, 그 페이지에서
    새로 찾은 것까지만 담고 멈춘다 (첫 글이 이미 아는 글이라고 페이지 안에서 바로
    멈추지는 않는다 — 상단 고정 글이 맨 위에 있는 게시판도 있어서, 그 아래 새 글이
    있는지는 페이지 끝까지 확인한다).

    이렇게 "페이지 전체가 새 글일 때만 다음 페이지로 넘어가는" 방식이 필요한 이유:
    사이트를 처음 등록할 때 1페이지만 시작점으로 채워둔 경우, 2페이지 이후는 한 번도
    저장한 적이 없는 "미지의 영역"이라서 known_links에 없다. 예전 방식대로 "한 페이지가
    통째로 새 글일 때만" 멈추면, 이런 사이트는 2페이지부터는 계속 "새 글처럼" 보여서
    안전 상한(MAX_INCREMENTAL_PAGES)까지 옛날 글을 몽땅 긁어올 수 있었다."""
    collected = []
    seen_links = set()
    for page in range(1, MAX_INCREMENTAL_PAGES + 1):
        rows = fetch_page(with_page(base_url, page))
        if not rows:
            break
        page_new = []
        hit_known = False
        for r in rows:
            if r["link"] in known_links:
                hit_known = True
                continue
            if r["link"] in seen_links:
                continue
            seen_links.add(r["link"])
            page_new.append(r)
        collected.extend(page_new)
        if hit_known or not page_new:
            break
        if page < MAX_INCREMENTAL_PAGES:
            time.sleep(REQUEST_DELAY_SEC)
    else:
        print(f"  [주의] {MAX_INCREMENTAL_PAGES}페이지까지 전부 새 글이라 더 있을 수 있음 (안전 상한 도달)")
    return collected


def fetch_new_notices(fetch_page, base_url, known_links, today):
    """known_links가 비어 있으면(이 사이트를 처음 추가한 경우) 초기 목록을 만들고,
    아니면(예전에 한 번 이상 수집한 사이트) 새로 올라온 글만 가져온다."""
    if not known_links:
        return bootstrap_notices(fetch_page, base_url, today)
    return fetch_incremental_notices(fetch_page, base_url, known_links)


def collect_site(site, my_keywords, existing_site, today):
    parser = PARSERS.get(site.get("parser", "").strip())
    prev_notices = existing_site["notices"] if existing_site else []

    if parser is None:
        print(f"  [건너뜀] {site['name']}: 등록된 파서가 없음 ({site.get('parser')})")
        return {"name": site["name"], "url": site["url"], "notices": prev_notices, "error": "파서 없음"}

    known_links = {n["link"] for n in prev_notices}

    try:
        new_rows = fetch_new_notices(parser, site["url"], known_links, today)
    except requests.RequestException as e:
        print(f"  [경고] {site['name']} 요청 실패: {e} (기존 데이터 유지)")
        return {"name": site["name"], "url": site["url"], "notices": prev_notices, "error": str(e)}

    if new_rows:
        print(f"  {site['name']}: 새 공지 {len(new_rows)}건 발견")
    else:
        print(f"  {site['name']}: 새 공지 없음")

    # 새 글 + 기존 글을 합치고, 최신 키워드 기준으로 관련 여부를 다시 계산한다.
    # (중복 방지: 혹시 new_rows에 기존과 겹치는 링크가 섞여 있어도 한 번만 남긴다.)
    existing_links = {n["link"] for n in prev_notices}
    merged = [n for n in new_rows if n["link"] not in existing_links] + prev_notices
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
    today = now.date()

    results = []
    for i, site in enumerate(sites):
        if i > 0:
            time.sleep(REQUEST_DELAY_SEC)
        results.append(collect_site(site, my_keywords, existing_by_name.get(site["name"]), today))

    reminders = load_reminders()
    results.extend(collect_reminders(reminders, existing_by_name, today))

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
