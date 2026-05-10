# txcp-crawl

m.thankqcamping.com 캠핑장 메타 크롤러. **camfit-puller 와 동급의 사이트 어댑터**.

본 패키지는 후속 PR 에서 루트 `crawlers/` 로 이동될 예정 — 현재는 `crawlers/` 분리 *직전 단계* 의 2번째 어댑터 도입 (Rule of Three 의 2 단계).

## 설치 / 빌드

```pwsh
cd txcp-crawl
uv sync
```

Python ≥3.11. dev 의존 추가 시 `uv sync --extra dev`.

## 빠른 사용

```pwsh
# 단일 카테고리 2 페이지
uv run python -m txcp_crawl.cli pull --site-tp BB000 --max-pages 2

# 전체 카테고리 풀 풀 (~17 분)
uv run python -m txcp_crawl.cli pull

# 디버그용 단일 페이지 dump
uv run python -m txcp_crawl.cli inspect-page 1 --site-tp BB000

# data/camps.jsonl → data/camps.csv 일괄 재생성
uv run python -m txcp_crawl.cli dedup-csv
```

출력 (`data/`):
- `camps.jsonl` — raw + 보정. 1 줄 = 1 record.
- `camps.csv` — camfit-puller 와 통합 가능한 공통 컬럼 (`source` 컬럼 추가).
- `state.json` — `last_page`, `total_seen`. 재실행 시 거기부터 resume.

## 카테고리 코드

| 코드 | 의미 |
|---|---|
| BB000 | 오토캠핑 |
| BB001 | 글램핑 |
| BB002 | 카라반 |
| BB003 | 펜션 |
| BB006 | 피크닉 |

## 사이트 구조 (사전 조사)

`POST /resv/ax_list_search.hbb` 가 직접 JSON 응답:

```json
{"code":200, "data":{"totalCount":9217, "campList":[Camp×20]}}
```

전체 카탈로그 ~9,217 건 (2026-05-10 기준), 페이지 사이즈 20, ~461 페이지.
robots.txt 전체 허용. 자세한 내용은 `.ShipofTheseus/txcp-crawl/intent/probes/FINDINGS.md`.

## 2-tier fetcher (상세)

본 PR 의 primary path = **`HttpxFetcher`** — 가볍고 빠름 (페이지당 ~0.5s).

향후 사이트가 STC Lab Bot Manager 등으로 AJAX 호출을 게이팅하기 시작하면, 같은 `Fetcher` Protocol 을 구현하는 **`ChromeFetcher`** (Playwright/Camoufox cloak chrome) 를 fallback 으로 발동.
- 본 PR 에서는 `ChromeFetcher` 가 placeholder (NotImplementedError + 안내).
- 발동 트리거: 4xx 비율 임계 (코드 안 가드) 또는 사용자 명시 옵션.
- 발동 시 의존: `playwright>=1.44` (`uv sync --extra playwright` + `playwright install chromium`).

## 정중함 (Polite)

- UA pool ≥5 (camfit-puller V-1 만족), 페이지당 1.5–3.0s jittered delay.
- robots.txt 자율 준수.
- 5xx/transport error 는 tenacity exp backoff 3회 재시도.
- 4xx 가 페이지 10 윈도우에 ≥2 발견 시 자동 break + state save.

## 환경변수 (옵션, prefix `TXCP_`)

| 키 | default |
|---|---|
| TXCP_DATA_DIR | `data` |
| TXCP_DELAY_MIN | `1.5` |
| TXCP_DELAY_MAX | `3.0` |
| TXCP_LOG_LEVEL | `INFO` |
| TXCP_MAX_PAGES_DEFAULT | `600` |
| TXCP_LIVE | (1 = smoke test 활성) |

## 테스트

```pwsh
uv run pytest -m "not live" -v
TXCP_LIVE=1 uv run python -m pytest tests/smoke_txcp_real.py -v
```

## camfit-puller 와의 관계

- camfit-puller `src/camfit_puller/` 의 stealth/csv/models 패턴을 *vendor + 일반화* (path 의존 회피, 후속 분리 자유도 우선).
- 후속 분리 시 본 패키지의 모듈 매핑:
  - `crawlers/_shared/` ← models / stealth / csv_writer / state
  - `crawlers/txcp/` ← adapter / crawler / cli (사이트 종속)
- camfit-puller 는 본 작업에서 *손대지 않음*.

## 후속 작업 (out-of-scope of this PR)

- `crawlers/` 루트 신설 + 양 패키지 mv.
- detail 페이지 scrape (URL 패턴 미상 — `clkCampPr` JS 함수 추적 필요).
- 좌표 (lat/lon) 보강.
- camfit + txcp entity resolution.
