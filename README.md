# 인천대 알림 모음 사이트

## 한 줄 목표

인천대학교 여러 사이트의 새 공지를 매일 자동으로 모으고, 내 학과와 관련 없는 공지는 접어서 보여주는 웹사이트를 만든다. (`auto-update-site` 스킬 기반: GitHub Actions로 매일 수집 → GitHub Pages로 무료 공개)

## 작업 카드

```text
목표: 인천대 공지 사이트를 매일 자동으로 스크래핑해서 최신 글을 모으고, 다른 학과 전용 공지는 걸러서 보여주는 웹사이트를 GitHub Pages로 공개하기
입력: 사용자가 보내줄 공지 사이트 목록 (input/sites.csv), 내 학과 키워드 (input/my_keywords.txt)
출력: docs/index.html (GitHub Pages로 공개되는 실제 웹사이트), data/data.json (수집 데이터)
성공 기준: 매일 아침 8시(KST) GitHub Actions가 자동으로 실행되어 사이트가 최신 공지로 갱신된다
오늘 만든 버전: 로컬 스크립트 완성(collect.py + build_site.py) + GitHub Actions 워크플로 작성. 실제 GitHub 배포는 아래 "GitHub 배포 절차"대로 진행 필요
```

## 구조

```text
incheon-univ-notices/
├── input/
│   ├── sites.csv          ← 수집할 사이트 목록 (사람이 관리)
│   └── my_keywords.txt    ← 내 학과 키워드 (사람이 관리)
├── data/
│   └── data.json          ← 수집된 공지 데이터 (collect.py가 매일 갱신)
├── src/
│   ├── collect.py         ← 사이트 스크래핑 + 학과 필터링 → data.json 저장
│   └── build_site.py      ← data.json → docs/index.html 생성
├── docs/
│   └── index.html         ← 실제 공개되는 웹사이트 (GitHub Pages)
└── .github/workflows/
    └── update.yml         ← 매일 08:00 KST 자동 실행
```

## 만들 기능

- [x] 인천대 홈페이지 공지사항 게시판 실제 스크래핑
- [x] 내 학과 관련 없는 공지 걸러내기 (input/my_keywords.txt 기반)
- [x] data.json / docs/index.html 분리 구조로 재구성 (auto-update-site 스킬 표준 구조)
- [x] GitHub Actions 워크플로 작성 (매일 08:00 KST, Gemini 등 AI 분석 없이 순수 스크래핑만 사용)
- [ ] **GitHub 저장소 생성 + 첫 배포** (사람이 해야 하는 단계, 아래 참고)
- [ ] 다른 인천대 공지 사이트 추가
- [ ] 필터링 정확도 다듬기

## GitHub 배포 절차 (아직 안 한 상태 - 꼭 필요한 단계)

이 스킬은 브라우저에서 GitHub 저장소를 만드는 과정이 필요하다. 이 컴퓨터에는 `gh`(GitHub CLI)가 설치되어 있지 않아서, 저장소 생성만은 직접 해줘야 한다. 나머지(커밋/푸시/Actions 설정)는 Codex가 도와줄 수 있다.

1. **GitHub에서 새 저장소 만들기**
   - github.com → 우측 상단 **+** → **New repository**
   - Repository name: `incheon-univ-notices` (또는 원하는 이름)
   - **Public** 선택 (Pages 무료 사용 조건)
   - "Add a README file" 체크 **해제**
   - Create repository
2. 저장소를 만들었으면 Codex에게 "저장소 만들었어, 주소는 https://github.com/[아이디]/incheon-univ-notices.git 이야, 이제 push 해줘"라고 알려주면 이 폴더를 그 저장소로 커밋/푸시한다.
3. **GitHub Pages 켜기**: 저장소 → Settings → Pages → Source: `Deploy from a branch` → Branch: `main` / Folder: `/docs` → Save
4. **첫 수동 실행 테스트**: 저장소 → Actions 탭 → "자동 업데이트" → Run workflow (한 번 눌러서 정상 동작 확인)
5. 몇 분 후 `https://[아이디].github.io/incheon-univ-notices` 에서 사이트 확인

이후에는 매일 08:00 KST에 GitHub Actions가 자동으로 `collect.py` → `build_site.py`를 실행하고, 바뀐 내용이 있으면 자동 커밋 + 배포한다.

## 로컬 실행 방법 (테스트용)

```powershell
python src/collect.py
python src/build_site.py
```

`docs/index.html`을 더블클릭해서 브라우저로 열어보면 결과를 바로 확인할 수 있다.

## 확인 방법

- **로컬**: `docs/index.html`을 열어서 "나와 관련된 공지" / "다른 학과 공지(접힘)" 분류가 맞는지 확인
- **배포 후**: `https://[아이디].github.io/incheon-univ-notices` 접속 + 저장소 Actions 탭에서 매일 초록색 체크(✅) 확인

## Codex에게 다음에 요청할 말

```text
저장소 만들었어, 주소는 https://github.com/[아이디]/incheon-univ-notices.git 이야, push 해줘.
```

```text
사이트 추가: 사이트명 - URL
```

```text
"OO공지가 나랑 관련 있는데 다른 학과로 잘못 분류됐어" 처럼 잘못된 필터링 결과 알려주기
```

## 메모

- **데이터 방식**: 트렌드 추적형(auto-update-site 기본 예시)과 달리, 이 프로젝트는 공지 게시판을 "매번 최신 스냅샷으로 교체"하는 방식이다. 게시판 자체가 이미 최신 글을 보여주므로, 과거 데이터를 계속 쌓아두지 않는다.
- **AI 분석 미사용**: `auto-update-site` 템플릿은 기본적으로 Gemini API로 데이터를 분석하지만, 이 프로젝트는 학과 이름 패턴 매칭만으로 충분해서 AI 호출 없이 만들었다. API 키/Secret 등록이 필요 없다.
- **필터링 한계**: "HUSS포용사회이니셔티브학부"처럼 이름 끝이 "학부"로 끝나지만 실제로는 전교생 대상인 공지가 다른 학과로 잘못 접힐 수 있다. 걸러진 공지도 숨기지 않고 펼쳐보기로 항상 확인 가능하게 해뒀다.
- **저장소 분리 이유**: 메인 워크스페이스(BAI-GUIDE) 저장소는 개인 메모 등 비공개 성격 파일이 섞여 있어서, 공개 웹사이트로 배포되는 이 프로젝트는 별도의 전용 저장소로 분리하기로 했다 (사용자 확인 완료). 메인 저장소의 `.gitignore`에 이 폴더가 추가되어 있다.
- 학교 사이트에 과도하게 자주 요청을 보내지 않도록 사이트별 요청 사이에 1초 딜레이를 넣어뒀다.
