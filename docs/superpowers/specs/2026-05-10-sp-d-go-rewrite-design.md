# SP-D — be-api Go rewrite + etago absorption

**Date**: 2026-05-10
**Status**: design approved, awaiting implementation plan
**Author**: superpowers brainstorming session
**Companion**: Sprint D-0 PoC gate determines whether SP-D proceeds or fallbacks to ML sidecar (separate spec).

## 1. Goal

현재 백엔드 토폴로지:
- `cf-be-api` (Python FastAPI :8071) — DB-tier, 18 use cases, 12 adapters
- `cf-be-for-fe` (Python FastAPI :8070) — BFF
- `etago` (Go binary) — 매 ETA·geocode 호출마다 subprocess fork
- ML — sentence-transformers (ko-sroberta), Python in-process

본 작업은:
1. **be-api 전체를 Go 로 재작성** — chi router + pgx + falkordb-go + ONNX runtime
2. **etago 흡수** — `etago/internal/route` 의 kakao/naver/osrm Go 코드를 새 Go be-api 의 adapters 로 이전. CLI + 별도 바이너리 제거. subprocess 제거.
3. **ML ONNX 래퍼** — ko-sroberta → ONNX export → Go onnxruntime. Python ML 의존 제거.

목적:
- **성능**: subprocess 제거, native Go 동시성, 단일 바이너리 메모리 효율
- **운영 단순화**: 4 프로세스 (BFF + Python be-api + etago + Python ML) → 2 프로세스 (BFF + Go be-api)
- **단일 언어 백엔드** (BFF 만 Python 잔존, BFF 는 얇아서 향후 결정)

## 2. Out of scope

- **fe 변경 없음** — Go be-api 는 BFF 와 동일 HTTP 컨트랙트 유지. BFF 도 변경 없음 (URL/포트 동일).
- **alembic / DB schema 변경 없음** — alembic 도구는 Python 그대로 (별도 패키지). Go be-api 는 schema 안 만짐.
- **Pipeline 변경 없음** — Python `cf_pipeline` 그대로. txcp/camfit 크롤러 무관.
- **BFF Go 화** — out of scope. BFF 는 얇아서 후속 결정.
- **monitoring/Slack/auth 추가** — 본 spec 범위 외.
- **다중 region / canary 배포** — Big bang cutover. 점진 배포는 후속.

## 3. Architectural decisions

| 결정 | 선택 | 트레이드오프 |
|---|---|---|
| 흡수 범위 | be-api 전체 Go 재작성 + etago 흡수 | 하이브리드 (Python 유지 + etago 흡수만): 작지만 ML 의존 + subprocess 절반만 해결 |
| ML 처리 | ONNX 래퍼 (ko-sroberta → ONNX → Go onnxruntime) | ML sidecar Python: 4 서비스 유지 / Drop semantic search: 기능 손실 |
| 마이그레이션 | Big bang | Strangler: 양쪽 동시 운영 부담 |
| 검증 | Sprint D-0 PoC 먼저 | PoC 없이 진행: ONNX 실패 시 SP-D 중반 폐기 위험 |
| 작업 위치 | git worktree (`D:/github/cf-go`) | 기존 main 워크트리: Python 운영 코드와 충돌 |
| Web framework | `chi` | gin/echo: 더 무거움, fiber: stdlib 비호환 |
| Postgres | `pgx/v5 + pgxpool` (pgvector) | database/sql: 더 무거움, gorm: 과잉 |
| FalkorDB | `FalkorDB/falkordb-go` (D-1 검증) | REST 직접: client 미성숙 시 fallback |
| Tokenizer | `sugarme/tokenizer` (D-0 우선 시도) | `daulet/tokenizers` (Rust binding, cgo): 정확 but 무거움 |
| ONNX runtime | `yalue/onnxruntime_go` (D-0 우선) | `wasilibs/go-onnxruntime`: WASI |

## 4. Final directory layout

```
D:\github\cf\
├── backend/
│   ├── be-api-go/                            # NEW (D-1 신규 in worktree)
│   │   ├── go.mod
│   │   ├── go.sum
│   │   ├── cmd/
│   │   │   └── be-api/
│   │   │       └── main.go                   # entrypoint
│   │   ├── internal/
│   │   │   ├── domain/                       # Camp, FeaturedAxis, errors (Go structs)
│   │   │   │   ├── models.go
│   │   │   │   ├── errors.go
│   │   │   │   ├── featured_axes.go          # FEATURED_AXES registry
│   │   │   │   ├── concept_seeds.go
│   │   │   │   └── camping_filter.go         # P6 predicate (포팅)
│   │   │   ├── ports/                        # interfaces (Go interface)
│   │   │   │   ├── repo.go
│   │   │   │   ├── graph.go
│   │   │   │   ├── embed.go
│   │   │   │   ├── eta.go
│   │   │   │   ├── geocode.go
│   │   │   │   ├── source.go
│   │   │   │   └── vector.go
│   │   │   ├── usecases/                     # 18 services 포팅
│   │   │   │   ├── list_camps.go
│   │   │   │   ├── get_site_detail.go
│   │   │   │   ├── semantic_search.go
│   │   │   │   ├── eta_for_fleet.go
│   │   │   │   └── ... (~14 more)
│   │   │   ├── adapters/
│   │   │   │   ├── postgres/
│   │   │   │   │   ├── pool.go
│   │   │   │   │   ├── camp_repo.go
│   │   │   │   │   ├── concept_repo.go
│   │   │   │   │   └── ... (theme/filter/signal/...)
│   │   │   │   ├── falkor/
│   │   │   │   │   └── graph.go
│   │   │   │   ├── pgvector/
│   │   │   │   │   └── search.go
│   │   │   │   ├── embed/                    # ONNX
│   │   │   │   │   ├── onnx_model.go
│   │   │   │   │   └── tokenizer.go
│   │   │   │   ├── eta/                      # 흡수: etago/internal/route/{naver,osrm}.go
│   │   │   │   │   ├── naver.go
│   │   │   │   │   └── osrm.go
│   │   │   │   ├── geocode/                  # 흡수: etago/internal/route/kakao.go
│   │   │   │   │   └── kakao.go
│   │   │   │   └── source/
│   │   │   │       └── jsonl_replay.go
│   │   │   ├── api/                          # chi router + handlers
│   │   │   │   ├── router.go
│   │   │   │   ├── healthz.go
│   │   │   │   ├── sites.go
│   │   │   │   ├── facets.go
│   │   │   │   ├── concepts.go
│   │   │   │   ├── themes.go
│   │   │   │   ├── marks.go
│   │   │   │   ├── eta.go
│   │   │   │   ├── admin.go
│   │   │   │   └── graph.go
│   │   │   └── settings/
│   │   │       └── config.go                 # envconfig
│   │   ├── tests/                            # _test.go 옆 통합
│   │   │   └── fixtures/
│   │   │       └── regression/               # JSON fixtures (Python 과 공유)
│   │   └── README.md
│   ├── be-api/                               # Python — D-7 까지 운영, D-8 cutover 시 제거
│   └── be-for-fe/                            # Python BFF — 변경 없음
├── etago/                                    # D-5 에서 internal/* 코드 이전, D-8 cutover 시 디렉터리 제거
├── ...
```

## 5. 흡수 매핑 (etago Go → be-api-go)

| etago 원본 | be-api-go 위치 | 비고 |
|---|---|---|
| `etago/internal/route/kakao.go` | `internal/adapters/geocode/kakao.go` | Kakao Search API (place name → lat/lon) |
| `etago/internal/route/naver.go` | `internal/adapters/eta/naver.go` | NCP Directions5 (drive ETA) |
| `etago/internal/route/osrm.go` | `internal/adapters/eta/osrm.go` | OSRM fallback |
| `etago/internal/route/provider.go` | `internal/adapters/eta/provider.go` | provider 인터페이스 |
| `etago/internal/route/route.go` | `internal/usecases/eta_for_fleet.go` | 일부 통합 |
| `etago/internal/parse/*.go` | `internal/adapters/{eta,geocode}/parse.go` | 응답 파싱 헬퍼 |
| `etago/internal/duration/*.go` | `internal/adapters/eta/duration.go` | 분 변환 |
| `etago/internal/envfile/*.go` | (제거) `envconfig` 으로 대체 | be-api 전체 envconfig 일관 |
| `etago/cmd/etago/main.go` | (제거) | CLI 불필요 |
| `etago/internal/route/*_test.go` | `internal/adapters/{eta,geocode}/*_test.go` | 그대로 마이그레이션 |
| `backend/be-api/src/cf_be_api/adapters/eta/etago_subprocess.py` | (제거) | subprocess 제거 |
| `backend/be-api/src/cf_be_api/adapters/geocode/etago_subprocess.py` | (제거) | subprocess 제거 |
| `backend/be-api/src/cf_be_api/adapters/etago_bin.py` | (제거) | auto-build resolver 불필요 |

## 6. 라이브러리 스택 (Go side)

| 영역 | 라이브러리 | 결정 sprint |
|---|---|---|
| HTTP 라우터 | `github.com/go-chi/chi/v5` | D-1 |
| Postgres | `github.com/jackc/pgx/v5` + `pgxpool` + `pgvector/pgvector-go` | D-1 |
| FalkorDB | `github.com/FalkorDB/falkordb-go` (smoke 통과 시) 또는 raw redis client | D-1 검증 |
| HTTP client | stdlib `net/http` (etago 그대로) | D-5 |
| ONNX runtime | `github.com/yalue/onnxruntime_go` (D-0 결정) | D-0 |
| Tokenizer | `github.com/sugarme/tokenizer` (D-0 결정) | D-0 |
| 설정 | `github.com/kelseyhightower/envconfig` | D-1 |
| 로깅 | stdlib `log/slog` (Go 1.21+) | D-1 |
| 테스트 | stdlib `testing` + `github.com/stretchr/testify/assert` | D-1 |
| Migration 도구 | (제외) — alembic Python 별도 유지 | — |

## 7. 서비스 토폴로지 변화

```
BEFORE                                  AFTER
┌──────────┐                             ┌──────────┐
│   fe     │                             │   fe     │
└────┬─────┘                             └────┬─────┘
     │                                        │
     ↓ HTTP                                   ↓ HTTP
┌──────────┐                             ┌──────────┐
│ BFF :8070│                             │ BFF :8070│
│ (Python) │                             │ (Python) │
└────┬─────┘                             └────┬─────┘
     │ HTTP                                   │ HTTP
     ↓                                        ↓
┌──────────────┐                         ┌──────────────┐
│ be-api :8071 │                         │ be-api :8071 │
│  (Python)    │                         │   (Go)       │  ← 단일 바이너리
└────┬─────────┘                         └────┬─────────┘
     │ subprocess                             │ direct
     ↓                                        ↓
┌──────────┐                             Kakao + NCP
│ etago.exe│                             PG + falkor
│  (Go)    │                             ONNX (in-process)
└──┬───────┘
   ↓ HTTP
Kakao + NCP
   +
PG + falkor (be-api 직접)
   +
sentence-transformers (Python in-process)
```

## 8. Sprint 구조 (D-0 ~ D-8)

| Sprint | 작업 | 검증 게이트 |
|---|---|---|
| **D-0** | **ONNX PoC** — ko-sroberta → ONNX export, sugarme/tokenizer + yalue/onnxruntime_go (또는 대체) 로 Go inference, 50개 한글 샘플에 대해 cosine 비교 | cosine 평균 ≥ 0.99, min ≥ 0.95. 실패 시 SP-D 중단 |
| **D-1** | Go 워크스페이스 셋업 — go.mod, cmd/be-api/main.go, chi, /healthz, settings, slog. **FalkorDB Go client maturity smoke** (connect + GRAPH.QUERY) | `go build` PASS, `go test ./...` PASS, /healthz 200, falkor smoke OK (혹은 fallback 결정) |
| **D-2** | domain + ports + adapters/postgres + adapters/falkor + adapters/source. CampReader/GraphReader 인터페이스 + 구현. | Go list_camps 결과가 Python 동일 query 결과와 동일 ID 셋 (10 시나리오) |
| **D-3** | adapters/embed (D-0 흡수) + usecases/semantic_search + handlers /sites/search, /sites/{id}/similar | Python `/sites/search?q=강원` 결과와 Go 결과 top-10 ID 일치율 ≥ 0.95 |
| **D-4** | 사용자-읽기 엔드포인트 일괄 — /sites, /sites/{id}, /facets, /concepts*, /themes*, /marks*, /featured-axes. camping_filter (P6) 도메인 predicate 포팅. | 모든 엔드포인트 응답 byte-수준 동일 (regression fixtures 재활용 + 신규 캡처) |
| **D-5** | etago 흡수 — `etago/internal/{route,parse,duration}/*.go` → `be-api-go/internal/adapters/{eta,geocode}/`. 기존 etago Go 테스트 동반 이전. /eta, /eta/batch, /eta/cache 핸들러 + use case (eta_for_fleet) | etago Go 테스트 100% pass, /eta/batch 동일 origin/dest 에 Python 결과와 분 (±1) 일치 |
| **D-6** | 어드민 + 그래프 — /admin/rebuild-graph, /admin/reembed, /graph/schema, /graph/sample, /graph/expand, /graph/search | graph.html 어드민 페이지 정상 렌더 (Go be-api 직접 호출) |
| **D-7** | 통합 테스트 + 성능 벤치 — Python (잠시 :8074 로 띄움) vs Go (:8071) cross-validate. ETA batch 1000건, embedding 100건, sites 풀 fetch latency 비교 → `docs/sp-d-performance-baseline.md` | Go ≥ Python (모든 워크로드). 동일 응답 (또는 명시된 차이) |
| **D-8** | **Cutover** — `scripts/dev-up.sh` 가 Go 바이너리 부팅. `backend/be-api/` Python 패키지 제거. `etago/` 디렉터리 제거. 워크스페이스 pyproject members 정리. BFF settings 변경 없음. **fallback 모드** (`FALLBACK_PYTHON_BE_API=1` 시 alembic 디렉터리 옆에 Python 흔적 보존 OR git revert one-shot 수단) | 모든 fe 트래픽 Go 통과. Python 흔적 0 (alembic 도구만 잔존). 풀 smoke. |

## 9. D-0 PoC 통과 기준 (gate)

- 50개 한글 샘플 (캠핑장 이름·설명·태그 다양체)
- Python: `SentenceTransformer("jhgan/ko-sroberta-multitask").encode(s)` 결과 임베딩 캡처 (768-dim float32 배열)
- Go ONNX: 동일 모델 + 동일 토크나이저 + 동일 입력 → 동일 임베딩
- **메트릭**:
  - cosine 평균 ≥ 0.99
  - cosine min ≥ 0.95
  - 실패 시: SP-D 중단, ML sidecar 옵션으로 별도 spec
- **결정 산출물**:
  - tokenizer 라이브러리 결정 + 이유
  - ONNX runtime 라이브러리 결정 + 이유
  - 변환 스크립트 보존 (`scripts/export-ko-sroberta-onnx.py`)

## 10. 워크트리 전략

```bash
# spec 머지 후, plan 단계 진입 시
cd D:/github/cf
git worktree add D:/github/cf-go -b feature/sp-d-go-rewrite
```

**운영**:
- D-0~D-7 모든 implementation 은 `D:/github/cf-go` 에서.
- 각 sprint = 작은 commit. PR 단위는 sprint 단위, base = `main`.
- D-7 까지 main 의 Python be-api 운영 그대로. Go be-api 는 별도 포트 (`:8073`) 검증 모드 (BFF 호출은 Python 으로 유지).
- D-8 cutover PR 에서 BFF mount + scripts 변경 + Python 패키지 제거. 이때 main merge.

**Spec/plan 문서**: `main` 의 `docs/superpowers/` (지금까지 패턴 동일).

## 11. 위험·미결 사항

| 위험 | 완화 |
|---|---|
| ONNX 정확도 게이트 | D-0 자체가 게이트 |
| FalkorDB Go client 미성숙 | D-1 검증, falkor REST API 직접 wrapper fallback |
| sentencepiece tokenizer Go 포팅 — Rust binding 의존 가능성 | D-0 sugarme 우선, 실패 시 daulet (cgo) |
| pytest fixture (회귀) Go 활용 | JSON fixture 언어 무관, D-2 부터 cross-validate |
| Big bang break 위험 | D-8 cutover 전 D-7 통합 검증, fallback PR (Python 복구 one-shot revert 가능) |
| alembic Python 도구 vs Go 서비스 | DB schema 책임 alembic 그대로 — 별도 패키지 유지 |
| pydantic models → Go structs | json struct tag, alias 정책, fixture 비교 자동 검출 |
| Cutover PR (D-8) 큰 변경 | 사용자 명시 승인 단계 추가 (auto-merge 대신 manual approval) |
| OS 다양성 (Windows/Linux) | etago 가 이미 다중 OS 빌드 — 그 패턴 재사용. CI matrix 권장 (후속) |

## 12. 결정의 의미 (다시 한 번)

이 디자인은 Big bang 이양 + ONNX 의존을 채택한다. 즉:
- D-0 PoC 가 SP-D 의 fate gate. 실패 시 SP-D 중단, ML sidecar 별도 spec 으로 재설계.
- D-8 cutover 가 단일 위험 시점. 실패 시 git revert 로 복구. fallback 정책 (Python 흔적 일시 보존) 명시.
- 워크트리는 main 운영을 보호하지만, D-8 cutover PR 은 main 에 큰 변경 — 사용자 manual approval 단계 추가 필요.

## 13. Next steps

본 spec 승인 후:
1. `superpowers:writing-plans` 스킬로 SP-D implementation plan 작성. plan 은 sprint D-0~D-8 단위 TODO + 검증 게이트 + 워크트리 부팅 절차 + 각 sprint cross-validation 명령 명시.
2. 워크트리 생성 (D-0 sprint 시작 시점).
3. D-0 PoC 결과로 D-1+ 진입 여부 결정.
