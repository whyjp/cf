# Repo restructure — crawl/ + backend/ + pipeline/ + scripts/

**Date**: 2026-05-10
**Status**: design approved, awaiting implementation plan
**Author**: superpowers brainstorming session

## 1. Goal

camfit-puller 가 *크롤러 + 백엔드(FastAPI/clean-arch/DB) + 후처리 파이프라인* 모두를 한 패키지에 담고 있어 (a) 후속 사이트 어댑터 추가가 어렵고 (b) 운영 boundary 가 모호함. 본 작업은 다음을 수행한다:

1. 크롤러를 `crawl/{camfit,txcp}/` 로 분리 (camfit + txcp 동형 구조; tkcp-crawl 은 txcp 로 rename).
2. 백엔드를 `backend/` 로 분리 (FastAPI + DI + clean-arch 4 layers).
3. 후처리 파이프라인을 `pipeline/` 로 분리 (jsonl → postgres → falkor + etago geocode + lexicon/seed).
4. 운영 sh 스크립트를 루트 `scripts/` 에 신설 (DB / backend / crawl×2 / migrate).
5. 4 패키지를 **uv workspace** 단일 lock + 단일 venv 로 묶음.
6. **연동 무결성 보장** — 매 단계 import path 정합성 + 테스트 PASS 유지.

## 2. Out of scope

- camfit-puller 의 graph schema 변경.
- fe/ 변경.
- etago Go binary 변경.
- docker-compose 의 service 정의 변경 (compose 파일은 그대로 사용).
- 기존 크롤된 데이터 (camfit-puller/data) 의 schema 변경.

## 3. Final directory layout

```
D:\github\cf\
├── pyproject.toml                # NEW workspace root (build 미배포)
├── uv.lock                       # NEW single lock
├── .venv/                        # single venv (gitignored)
├── .run/                         # NEW gitignored — pid + log files
├── crawl/
│   ├── camfit/                   # MOVED from camfit-puller (crawl-only)
│   │   ├── pyproject.toml        # name: camfit-crawl
│   │   ├── README.md
│   │   ├── src/camfit_crawl/     # (former camfit_puller, crawl subset)
│   │   │   ├── __init__.py
│   │   │   ├── cli.py
│   │   │   ├── settings.py
│   │   │   ├── models.py
│   │   │   ├── parser.py
│   │   │   ├── stealth.py
│   │   │   ├── csv_writer.py
│   │   │   ├── etago_adapter.py  # geocode call stub (production = pipeline)
│   │   │   └── crawler.py
│   │   ├── scripts/              # cf_pull_*.py / cf_dedup_to_csv / cf_grab / cf_inspect_*
│   │   ├── tests/                # crawler-only tests
│   │   └── data/                 # gitignored
│   └── txcp/                     # RENAMED from tkcp-crawl
│       ├── pyproject.toml        # name: txcp-crawl
│       ├── README.md
│       ├── src/txcp_crawl/       # package rename: tkcp_crawl → txcp_crawl
│       ├── tests/
│       └── data/
├── backend/                      # NEW from camfit-puller backend portion
│   ├── pyproject.toml            # name: cf-backend
│   ├── src/cf_backend/
│   │   ├── __init__.py
│   │   ├── api.py
│   │   ├── container.py
│   │   ├── settings.py
│   │   ├── domain/
│   │   ├── ports/
│   │   ├── usecases/
│   │   └── adapters/             # falkor / postgres / pgvector / embed / source / extract / cluster / numpy_vector / eta / etago_bin / geocode
│   └── tests/                    # contract / integration / unit / graph_api / etc.
├── pipeline/                     # NEW from camfit-puller post-crawl scripts
│   ├── pyproject.toml            # name: cf-pipeline. workspace dep: cf-backend
│   ├── src/cf_pipeline/
│   │   ├── __init__.py
│   │   ├── ingest_camps.py       # jsonl → postgres camps upsert (source, id)
│   │   ├── rebuild_graph.py      # postgres → falkor
│   │   ├── geocode_run.py        # null lat/lon → etago binary
│   │   ├── derive_lexicon.py
│   │   ├── seed_concepts.py
│   │   ├── seed_filter_mapping.py
│   │   └── full_run.py           # orchestrator (scripts/migrate.sh entry)
│   └── tests/
├── scripts/                      # NEW root sh-only ops
│   ├── db-up.sh                  # docker compose up -d + healthcheck poll
│   ├── db-down.sh                # docker compose down (volume preserved)
│   ├── db-status.sh
│   ├── backend-up.sh             # nohup uvicorn + .run/backend.pid
│   ├── backend-down.sh           # pid → TERM → wait → KILL fallback
│   ├── crawl-camfit.sh
│   ├── crawl-txcp.sh
│   ├── migrate.sh                # cf_pipeline.full_run
│   ├── setup.sh                  # uv sync + db-up + backend-up
│   ├── teardown.sh               # backend-down + db-down
│   ├── dev-status.sh
│   ├── test.sh                   # all-packages pytest
│   └── lib/
│       ├── common.sh             # log helpers, pid utils
│       └── env.sh                # REPO_ROOT, DATA dirs, DB url defaults
├── docker/                       # UNCHANGED — falkordb + postgres compose
├── etago/                        # UNCHANGED — Go geocoder
├── fe/                           # UNCHANGED
└── docs/superpowers/
    ├── specs/2026-05-10-repo-restructure-design.md   # this file
    └── plans/                    # writing-plans output goes here
```

camfit-puller/ 디렉터리는 단계별 비워진 후 마지막 commit 에서 제거 (잔존 husk 없음).

## 4. Module mapping (camfit-puller → 어디로)

| 원본 (camfit-puller/) | 신 위치 |
|---|---|
| `src/camfit_puller/{crawler,parser,models,stealth,csv_writer,etago_adapter,cli,settings}.py` | `crawl/camfit/src/camfit_crawl/` |
| `scripts/cf_pull_*.py` `cf_dedup_to_csv.py` `cf_grab.py` `cf_inspect_*.py` `fetch_cf_home_scrapling.py` `_state_audit.py` `summarize_camfit_snapshot.py` | `crawl/camfit/scripts/` |
| `data/` | `crawl/camfit/data/` (gitignored) |
| crawler 관련 tests (`test_crawler_respx.py` `test_csv_writer.py` `test_parser.py` `test_stealth.py` `test_etago_adapter.py` `smoke_etago_geo.py`) | `crawl/camfit/tests/` |
| `src/camfit_puller/{api,container}.py` `domain/` `ports/` `usecases/` `adapters/` | `backend/src/cf_backend/` |
| backend 관련 tests (`tests/contract` `tests/integration` `tests/unit` `tests/test_graph_api.py`) | `backend/tests/` |
| `scripts/{migrate_to_pg,cf_load_rich,derive_lexicon,seed_concepts,seed_filter_mapping}.py` | `pipeline/src/cf_pipeline/` (포팅) |
| `scripts/cf_geocode.py` | `pipeline/src/cf_pipeline/geocode_run.py` |
| `tkcp-crawl/` (전체) | `crawl/txcp/` (rename pkg `tkcp_crawl` → `txcp_crawl`) |

## 5. uv workspace contract

루트 `pyproject.toml`:
```toml
[tool.uv.workspace]
members = ["crawl/camfit", "crawl/txcp", "backend", "pipeline"]

[tool.uv.sources]
cf-backend = { workspace = true }
```

각 패키지 `pyproject.toml`:
- `crawl/camfit/pyproject.toml` — gather only crawl deps (httpx, selectolax, pydantic, typer, loguru, tenacity).
- `crawl/txcp/pyproject.toml` — gather only crawl deps (이미 tkcp-crawl 의 정의 그대로 + 패키지명 rename).
- `backend/pyproject.toml` — fastapi, uvicorn, falkordb, psycopg, sqlalchemy, pgvector, alembic, sentence-transformers, sklearn, numpy + 위 crawl deps 일부 공유.
- `pipeline/pyproject.toml` — workspace dep `cf-backend`, plus light deps.

## 6. scripts/ catalog

| File | Behavior |
|---|---|
| `db-up.sh` | `cd "$REPO_ROOT/docker" && docker compose up -d` + 60s poll for both healthchecks |
| `db-down.sh` | `docker compose down` (no -v, volumes preserved) |
| `db-status.sh` | `docker compose ps` + `redis-cli -p 6379 ping` + `pg_isready -h localhost -U camfit -d camfit` |
| `backend-up.sh` | `nohup uv run uvicorn cf_backend.api:app --host 0.0.0.0 --port 8000 > .run/backend.log 2>&1 &` + write `.run/backend.pid` |
| `backend-down.sh` | read `.run/backend.pid` → SIGTERM → wait 10s → SIGKILL |
| `crawl-camfit.sh` | `uv run python -m camfit_crawl.cli pull "$@"` (passthrough args) |
| `crawl-txcp.sh` | `uv run python -m txcp_crawl.cli pull "$@"` |
| `migrate.sh` | `uv run python -m cf_pipeline.full_run --camfit-data crawl/camfit/data --txcp-data crawl/txcp/data "$@"` |
| `setup.sh` | `uv sync` + `db-up.sh` + `backend-up.sh` |
| `teardown.sh` | `backend-down.sh` + `db-down.sh` |
| `dev-status.sh` | `db-status.sh` + backend pid check + log tail |
| `test.sh` | each package `pytest -m "not live"` + 합 합산 |

`lib/env.sh`:
```sh
REPO_ROOT="${REPO_ROOT:-$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)}"
RUN_DIR="$REPO_ROOT/.run"
mkdir -p "$RUN_DIR"
DATABASE_URL_DEFAULT="postgresql://camfit:camfit@localhost:5432/camfit"
FALKORDB_URL_DEFAULT="redis://localhost:6379"
```

## 7. Migration pipeline contract (`cf_pipeline.full_run`)

순차:
1. `ingest_camps` — `crawl/{camfit,txcp}/data/camps.jsonl` 읽어 postgres `camps` 테이블 upsert. PK=(source, id). 기존 row 는 update (덮어쓰기 정책: pulled_at 더 새것 채택).
2. `geocode_run` — `lat IS NULL OR lon IS NULL` row 들 모아 etago 바이너리 호출 → `UPDATE camps SET lat, lon WHERE id`.
3. `rebuild_graph` — postgres 의 모든 camps row 를 falkor 그래프로 (Camp / Sido / Sigungu / SiteTp 노드 + LOCATED_IN / OF_TYPE 엣지).
4. `derive_lexicon` — 키워드 / 시노님 사전 갱신.
5. `seed_concepts` + `seed_filter_mapping` — 테마 시드 + 필터 매핑.

각 단계 idempotent. CLI 옵션:
- `--only ingest_camps` / `--only geocode_run` 등 특정 단계만.
- `--skip-geocode` / `--skip-graph` 등 단계 제외.
- `--dry-run`: 변경 없이 plan 출력.
- 로그: `.run/migrate.log`.

## 8. Migration sequencing (git history 보존)

각 단계는 단일 commit 으로 끝나며 매 commit 후 *전체 테스트 PASS* 보장.

| Sprint | 작업 | 테스트 게이트 |
|---|---|---|
| S1 | `pyproject.toml` 워크스페이스 루트 + `.gitignore` 보강 + `.run/` | `uv sync` 통과 |
| S2 | `tkcp-crawl/` → `crawl/txcp/` (git mv + 패키지 rename) | `crawl/txcp/` 자체 pytest 34/34 PASS |
| S3 | `camfit-puller/` 의 크롤러 코드 → `crawl/camfit/` (git mv + 패키지 rename `camfit_puller` → `camfit_crawl`) | `crawl/camfit/` 자체 pytest PASS (기존 테스트 적용) |
| S4 | `camfit-puller/data/` → `crawl/camfit/data/` (git mv) | data 파일 무결성 확인 (line count) |
| S5 | `camfit-puller/` 의 백엔드 코드 → `backend/src/cf_backend/` (git mv + import rewrite) | `backend/` 자체 pytest PASS |
| S6 | `camfit-puller/scripts/{migrate_to_pg,cf_load_rich,derive_lexicon,seed_*,cf_geocode}.py` → `pipeline/src/cf_pipeline/` (port + reuse usecases) | `pipeline/` 자체 pytest PASS |
| S7 | 루트 `scripts/*.sh` + `lib/{common,env}.sh` 작성 | `scripts/test.sh` PASS, `scripts/db-up.sh` smoke |
| S8 | `camfit-puller/` 잔여 husk 제거 | git status clean |
| S9 | 통합 검증 — `setup.sh` → `crawl-txcp.sh --max-pages 2` → `migrate.sh --dry-run` → `teardown.sh` | end-to-end smoke PASS |

매 sprint 의 import path rewrite 는 *영향받는 파일 그 안에서만* 변경 — 외부 패키지에서 import 하던 게 깨지면 즉시 수정.

## 9. Testing strategy (사용자 명시: "매 단계 테스트, 연동 보호")

원칙:
- **각 sprint 끝마다 모든 패키지 pytest "not live" 통과**. 깨지면 다음 sprint 시작 X.
- **새 import path 검증** — git mv + rename 직후 `python -c "import <new_path>"` 첫 게이트.
- **연동 무결성** — backend 가 crawl/{camfit,txcp} 의 model 을 import 하지 않도록 격리. pipeline 만 양쪽 jsonl 을 읽음.
- **smoke 보강** — sprint 7 후 `scripts/test.sh` 가 모든 패키지 pytest + scripts 자체 dry-run 검증.

신규 테스트:
- `pipeline/tests/test_ingest_camps.py` — fixture jsonl 2 개 (camfit + txcp) → in-memory postgres (testcontainers) → upsert 후 row 수 검증.
- `pipeline/tests/test_full_run_dry.py` — `--dry-run` 모드 종료코드 0 + plan 출력 contains 5 단계.
- `scripts/tests/` — 단순 sh assertions (외부 의존 없음): db-up.sh idempotent (재실행 OK), backend pid 파일 생성/제거, migrate.sh dry-run 종료코드 0. `scripts/tests/run.sh` 가 모든 sh 케이스 일괄.

기존 테스트 유지:
- crawl/camfit/tests — 패키지 rename 만 반영.
- crawl/txcp/tests — 동일.
- backend/tests — 패키지 rename + import path rewrite.

## 10. Risks + mitigations

| Risk | Mitigation |
|---|---|
| `git mv` 시 history 끊김 | git mv 사용 + 한번에 mv + 별도 commit (rename 검출 임계) |
| import path rewrite 누락 | sprint 단위 pytest collection 시점에 검출. 1 패키지씩 진행 |
| backend 의 deps 가 무거워 (sentence-transformers) workspace 단일 venv 비대 | 수용 (개발 편의 우선). 추후 split 옵션 |
| pipeline 의 usecases 가 backend 의 ports 에 의존 | workspace dep `cf-backend` 로 정상 import. 분리 후에도 유지 |
| crawl/camfit 의 etago_adapter 가 backend 의 etago port 와 중복 | 본 PR 에서는 양쪽 유지 (crawler 자체 etago stub + backend 의 production etago). pipeline 만 backend 사용. 후속 PR 에서 통합 검토 |
| docker-compose path 가 `cd docker` 가정 | scripts/lib/env.sh 의 REPO_ROOT 로 절대 path 보정 |
| Windows 네이티브에서 sh 실행 X | 사용자가 WSL 사용 동의 (sh 전용 결정). README 에 명시 |

## 11. Acceptance criteria

- [ ] 루트 `uv sync` 한방에 4 패키지 의존 설치 + 단일 lock.
- [ ] `crawl/camfit/`, `crawl/txcp/`, `backend/`, `pipeline/` 각자 pytest "not live" PASS.
- [ ] `scripts/db-up.sh && scripts/db-status.sh` PASS (docker 가용 시).
- [ ] `scripts/migrate.sh --dry-run` exit 0.
- [ ] `scripts/crawl-txcp.sh --max-pages 2` 가 종료 후 `crawl/txcp/data/camps.jsonl` 에 ≥40 줄 (재실행 시 0 신규).
- [ ] `camfit-puller/` 디렉터리 부재.
- [ ] git history — 주요 파일 (`crawler.py`, `models.py`, `csv_writer.py`, `stealth.py`) `git log --follow` 추적 가능.

## 12. Next step

본 디자인 승인 후 `superpowers:writing-plans` 스킬로 implementation plan 작성. plan 은 sprint S1–S9 단위 TODO + 각 sprint 의 verification 명령 + rollback 절차 명시.
