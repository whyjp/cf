# Backend split — be-api / be-for-fe (BFF pattern)

**Date**: 2026-05-10
**Status**: design approved, awaiting implementation plan
**Author**: superpowers brainstorming session
**Depends on**: `2026-05-10-repo-restructure-design.md` (S1–S9 마이그레이션 완료 가정)
**Companion specs (parallel sub-projects)**: SP-B/C — fe Vite 마이그레이션 + m.html 모바일 entry (별도 spec)

## 1. Goal

현재 `backend/src/cf_backend/` 단일 패키지가 (a) DB·falkor·pgvector·etago 직접 접근, (b) FastAPI 외부 노출, (c) FE-friendly projection (`_camp_to_fe_row`, `_filter_maritime_for_inland`, `_project_categories`, `_LANDLOCKED_SIDO`) 책임을 모두 가진다. 본 작업은 backend 를 두 uv workspace 패키지로 분리한다:

- **be-api** (`cf-be-api`): DB-tier. 도메인·ports·usecases·adapters + raw 도메인 응답 FastAPI. 프로덕션에서는 VPC 내부에서만 도달 가능.
- **be-for-fe** (`cf-be-for-fe`): BFF (Backend-For-Frontend). 외부 노출. fe 의 모든 트래픽이 진입. be-api 를 httpx 로 호출하고 FE-friendly 응답으로 가공·합성.

분리 목적:
1. **보안 강화** — DB 접근면을 BFF 만 가능. 프로덕션에서 be-api 인스턴스를 BFF subnet 에서만 도달 가능하도록 인프라(SG/firewall) 격리.
2. **모듈화** — projection·aggregation 책임이 BFF 로 명시적으로 이전. 도메인 코드는 raw 데이터 반환에 집중.
3. **fe 친화성** — BFF 가 향후 FE 요구에 맞춰 응답 형태를 변형해도 도메인 코드 영향 없음.

## 2. Out of scope

- **인증·인가** — 본 작업에서는 도입하지 않음. be-api 는 네트워크 도달성으로만 보호 (프로덕션 = VPC SG, 로컬 dev = 인증 없음). JWT·OIDC·세션은 후속.
- **캐싱·rate-limit·메트릭** — 얇은 BFF. Redis·slowapi·OTEL 도입은 후속.
- **gRPC 또는 GraphQL** — HTTP/REST 만. tailored 응답이 필요한 시점에 재고.
- **fe/ 변경** — fe/index.html, fe/m.html 의 base URL 은 그대로 8070 (BFF) 유지. fe/graph.html (어드민) 만 base URL 분리 (sprint A5).
- **mTLS·서비스 토큰** — 의도적으로 도입하지 않음. 이 결정의 의미: 로컬 dev 에서는 실제 보안 모델이 재현되지 않음. 받아들임.
- **graph schema·crawler·pipeline** — 변경 없음.

## 3. Architectural decisions (from brainstorming)

| 결정 | 선택 | 대안과의 트레이드오프 |
|---|---|---|
| 호출 프로토콜 | **HTTP/REST** | gRPC: 타입 안전·성능 좋으나 빌드 단계·디버깅 도구 추가. in-process import: VPC 격리 의도 무효화. |
| 레포 구조 | **같은 repo, uv workspace 2 패키지** | 별도 repo: 권한·CI·메인테이너 독립. 그러나 타입 공유 어려움, 현 규모에 과잉. |
| BFF 책임 | **얇음 — projection + aggregation 만** | 두꺼운 BFF: 인증·캐싱·rate-limit 포함. SP-A 스코프 폭발. |
| 서비스 간 인증 | **네트워크 계층만 (토큰 없음)** | mTLS: 보안 강함, 로컬 dev 복잡도 증가. 토큰: secret 순환 부담. |
| 어드민·그래프 라우팅 | **be-api 직접** | BFF 통과: 단일 출처. 그러나 BFF 가 의미 없는 thin proxy 코드 추가. |

## 4. Final directory layout

```
D:\github\cf\
├── backend/                              # 워크스페이스 그룹 디렉터리
│   ├── be-api/                           # ⭐ DB-tier
│   │   ├── pyproject.toml                # name = "cf-be-api"
│   │   ├── alembic/                      # MOVED from backend/alembic/
│   │   ├── alembic.ini                   # MOVED
│   │   ├── README.md
│   │   ├── tests/
│   │   └── src/cf_be_api/
│   │       ├── __init__.py
│   │       ├── api.py                    # FastAPI — raw 도메인 응답
│   │       ├── container.py              # DI (DB/falkor/pgvector/etago)
│   │       ├── settings.py
│   │       ├── domain/                   # MOVED from cf_backend/domain/
│   │       ├── ports/                    # MOVED from cf_backend/ports/
│   │       ├── usecases/                 # MOVED from cf_backend/usecases/
│   │       ├── adapters/                 # MOVED from cf_backend/adapters/
│   │       └── schemas/                  # NEW — Pydantic 모델, BFF 가 import
│   └── be-for-fe/                        # ⭐ BFF
│       ├── pyproject.toml                # name = "cf-be-for-fe"
│       │                                 # deps = ["cf-be-api", "httpx", "fastapi"]
│       ├── README.md
│       ├── tests/
│       └── src/cf_be_for_fe/
│           ├── __init__.py
│           ├── api.py                    # FastAPI — fe 친화 응답
│           ├── client.py                 # httpx.Client — be-api 호출
│           ├── projection.py             # _camp_to_fe_row, _filter_maritime_*, _project_categories
│           ├── aggregation.py            # 여러 be-api 호출 합성 (예: sites + marks)
│           ├── constants.py              # _LANDLOCKED_SIDO 등
│           └── settings.py               # BE_API_BASE_URL, allowed origins
├── crawl/                                # UNCHANGED
├── pipeline/                             # UNCHANGED
├── etago/                                # UNCHANGED
├── docker/                               # UNCHANGED
├── fe/                                   # ALMOST UNCHANGED — graph.html base URL 만 분리 (A5)
├── scripts/
│   ├── dev-up.sh                         # NEW — be-api + be-for-fe 동시 spawn
│   ├── dev-down.sh                       # NEW — 종료
│   ├── backend-up.sh                     # MODIFIED — be-for-fe 만 띄움 (단일 모드)
│   └── test.sh                           # MODIFIED — 두 패키지 모두 pytest
└── pyproject.toml                        # workspace root (members 갱신)
```

## 5. HTTP 엔드포인트 라우팅 매핑

| 현재 엔드포인트 | be-api 노출 | be-for-fe 노출 | fe 가 호출하는 곳 | BFF 처리 종류 |
|---|---|---|---|---|
| `/healthz` | ✓ | ✓ (자체) | 둘 다 (배포 헬스체크) | 자체 |
| `/sites` | ✓ raw 도메인 dict | ✓ projection | be-for-fe | **projection** (`_camp_to_fe_row`, `_filter_maritime_for_inland`, `_project_categories`) |
| `/sites/{id}` | ✓ raw | ✓ projection | be-for-fe | **projection** |
| `/sites/search` | ✓ raw | ✓ projection | be-for-fe | **projection** |
| `/sites/{id}/similar` | ✓ raw | ✓ projection | be-for-fe | **projection** |
| `/facets` | ✓ | ✓ | be-for-fe | **얇은 통과** |
| `/concepts`, `/concepts/{name}/camps` | ✓ | ✓ | be-for-fe | **얇은 통과** |
| `/themes`, `/themes/{id}/camps` | ✓ | ✓ | be-for-fe | **얇은 통과** |
| `/marks`, `/marks/{axis}/camps` | ✓ | ✓ | be-for-fe | **얇은 통과** (단 fe 가 marks/management/camps 도 호출 — 같이 노출) |
| `/featured-axes` | ✓ | ✓ | be-for-fe | **얇은 통과** |
| `/eta`, `/eta/batch`, `/eta/cache` (DELETE) | ✓ (etago 호출) | ✓ | be-for-fe | **얇은 통과** |
| `/admin/rebuild-graph`, `/admin/reembed` | ✓ | ❌ | **be-api 직접** (어드민, VPC 내부) | — |
| `/graph/schema`, `/graph/sample`, `/graph/expand`, `/graph/search` | ✓ | ❌ | **be-api 직접** (fe/graph.html, 어드민 전용) | — |

**얇은 통과**도 BFF 의 의미가 있음: (a) 단일 origin (CORS·도메인 정책 일원화), (b) 후속 캐싱·인증 진입점 자리 확보, (c) be-api API 가 변해도 fe 영향 격리.

## 6. 호출 흐름 (예: GET /sites)

```
브라우저 (https://camfit.example.com/m.html)
   │
   │ GET /sites?region=강원&concept=valley
   ▼
be-for-fe :8070 (외부 노출)
   │
   │ httpx.get(f"{BE_API}/sites?region=강원&concept=valley")
   ▼
be-api :8071 (VPC 내부, BFF subnet 에서만 도달 가능)
   │
   │ Container.list_camps(region="강원", concepts=["valley"])
   ▼
falkor 6379 + postgres 5432
   │
   ◄── raw [Camp.dict(), ...]   (도메인 형식)
be-api ── 응답: raw JSON 배열
   │
   ◄── be-for-fe.projection.camp_rows(raw, axes=...)
        ↳ _filter_maritime_for_inland(items, sido)
        ↳ _project_categories(collections, types)
        ↳ _camp_to_fe_row(c)
   │
be-for-fe ── 응답: FE-friendly JSON 배열
   ▼
브라우저 ── 렌더
```

## 7. 보안·배포 모델

### 7.1 프로덕션 (가정 — AWS 또는 GCP VPC)
- **be-api**: 내부 LB 또는 ClusterIP. 외부 LB·ALB 에 미노출. SG/firewall 규칙 = `from BFF subnet, port 8071, allow`. 그 외 거부.
- **be-for-fe**: 외부 LB/ALB 뒤. CORS = fe origin 화이트리스트.
- **be-api ↔ be-for-fe**: 평문 HTTP (TLS 종단은 외부 LB. VPC 내부 트래픽은 plain). 향후 mTLS 도입 시 v2.

### 7.2 로컬 dev
- `scripts/dev-up.sh` 가 be-api :8071 + be-for-fe :8070 을 백그라운드 spawn (stdout → `.run/be-api.log`, `.run/be-for-fe.log`).
- be-for-fe 의 env: `BE_API_BASE_URL=http://localhost:8071`.
- be-api 는 인증 없이 8071 직접 접근 가능 — **로컬에서는 보안 모델이 재현되지 않음을 받아들임**.
- `scripts/dev-down.sh` 가 PID 기반 종료.

### 7.3 fe 와의 호환성
- **fe/index.html, fe/m.html**: 변경 없음. `${API}/sites` 등 8070 호출 그대로. 사용자 입장에서 SP-A 는 보이지 않는 변경.
- **fe/graph.html**: base URL 만 별도 (어드민 모드). 환경변수 또는 URL 쿼리 (`?api=http://admin-internal:8071`) 로 주입. 어드민이 사내망에서 접근.

### 7.4 CORS
- be-for-fe 의 `_settings.allowed_origins` = fe public origin (배포 시점에 결정).
- be-api 는 CORS middleware 비활성. Origin 검사 없음 (내부 트래픽 가정).

## 8. 공유 타입

`cf-be-api` 의 `schemas/` 가 source-of-truth. `cf-be-for-fe` 가 uv workspace dep 으로 import:

```toml
# backend/be-for-fe/pyproject.toml
[project]
dependencies = [
    "cf-be-api",
    "fastapi",
    "httpx",
    "pydantic",
]

[tool.uv.sources]
cf-be-api = { workspace = true }
```

별도 `cf-shared` 패키지는 만들지 않음 (YAGNI — be-api 가 schemas 의 자연스러운 owner. 만약 schemas 를 도메인과 분리하고 싶을 때 재고).

## 9. 호출 클라이언트 (`cf_be_for_fe.client`)

```python
# 개략
class BeApiClient:
    def __init__(self, base_url: str, timeout_s: float = 12.0): ...

    def get_sites(self, *, region: str | None, concepts: list[str]) -> list[dict]: ...
    def get_site(self, site_id: str) -> dict: ...
    def get_facets(self) -> dict: ...
    def get_featured_axes(self) -> list[dict]: ...
    # ... (엔드포인트 매핑은 5절 표 참조)

    # 에러 처리: 5xx 또는 timeout → BeApiError 로 변환, BFF 핸들러가 503 으로 변환.
```

- 기본은 sync httpx (현재 cf_backend 핸들러도 sync). 향후 async 로 점진 전환.
- 재시도 정책 v1: 없음. 본격 도입은 v2.

## 10. 마이그레이션 Sprint (실행 순서)

| Sprint | 작업 | 검증 |
|---|---|---|
| **A1** | `backend/` 디렉터리 분할: 현 `backend/src/cf_backend/` → `backend/be-api/src/cf_be_api/` (git mv + 패키지 rename + import rewrite). alembic·alembic.ini → `backend/be-api/`. 워크스페이스 root pyproject members 갱신. | `cf-be-api` pytest PASS, `uv run --package cf-be-api uvicorn cf_be_api.api:app --port 8071` 부팅, `/healthz` 응답. |
| **A2** | `backend/be-for-fe/` 신규 패키지 + httpx client + healthz + 단순 통과 (`/facets`, `/concepts`, `/themes`, `/featured-axes`, `/marks*`). projection 없이 본문 그대로 패스스루. | `cf-be-for-fe` pytest PASS, BFF 가 8071 으로 facets fetch 성공, fe 가 8070 호출했을 때 정상 응답. |
| **A3** | projection 함수 이전 — `_camp_to_fe_row`, `_filter_maritime_for_inland`, `_filter_location_types_for_inland`, `_project_categories`, `_LANDLOCKED_SIDO` → `cf_be_for_fe/{projection,constants}.py`. be-api `/sites*` 핸들러는 raw 도메인 dict 만 반환하도록 정리. BFF 가 projection 적용. | `/sites` 응답 사전/사후 byte-수준 동일 (회귀 테스트: 셀렉트된 region·concept 조합 N개에 대해 fe 가 받는 응답 hash 비교). |
| **A4** | `/eta`, `/eta/batch`, `/eta/cache` (DELETE) BFF 통과. body 검증·timeout·동시성 정책은 be-api 가 그대로 가짐. | E2E: fe 에서 origin 입력 → ETA 적용 → 결과 표시 시나리오 PASS. |
| **A5** | `/graph/*`, `/admin/*` 는 be-for-fe 가 노출하지 않음. fe/graph.html 의 base URL 결정 — 환경변수 `?api=` 쿼리 우선, 없으면 동일 origin (어드민이 직접 be-api 호스트로 접근하는 경우). 문서화. | graph.html 페이지가 어드민 모드 (be-api 직접 호출) 에서 정상 동작. |
| **A6** | `scripts/dev-up.sh` (두 서비스 동시 spawn) + `scripts/dev-down.sh` + `scripts/test.sh` (두 패키지 pytest) | `dev-up.sh` → curl 8070 healthz + curl 8070 sites smoke PASS, `test.sh` 두 패키지 PASS. |
| **A7** | 잔여 husk 정리 — `backend/src/cf_backend/` 디렉터리 제거 확인, README 갱신 (camfit-puller serve 류 stale 명령 정리, 새 dev-up.sh 안내). | `git status` clean, `backend/README.md` + `backend/be-api/README.md` + `backend/be-for-fe/README.md` 일관. |

각 sprint commit 분리. 각 sprint 끝에서 검증 커맨드 실행 → 결과 evidence 와 함께 다음 sprint 진입.

## 11. 검증·롤백 정책

- **회귀 테스트 (A3 핵심)**: 사전 사진 — A2 완료 시점에 fe 가 받는 `/sites?region=...&concept=...` 응답을 fixture 로 캡처 (10개 조합). A3 후 BFF projection 통과한 결과가 byte-수준 동일.
- **롤백**: 각 sprint 는 단일 commit. 문제 발견 시 `git revert <hash>`. uv workspace 는 동시 lock 이라 revert 후 `uv sync` 한 번이면 복구.
- **단계별 cutover**: 별도 트래픽 분기 없음. 로컬·dev 환경에서 검증 후 단일 배포로 전환.

## 12. 위험·미결 사항

| 위험 | 완화 |
|---|---|
| projection 이전 시 응답 형태가 미세하게 달라질 수 있음 (예: dict 키 순서, None vs 누락) | A3 회귀 테스트 fixture 가 잡음. 차이 발견 시 BFF projection 에서 보정. |
| httpx sync vs async — 현재 cf_backend 핸들러 일부가 async (확인 필요), BFF 도 동일 정책 채택 필요 | A1 시점에 핸들러 async/sync 패턴 inventory. BFF client 는 동일 패턴. |
| 두 서비스 띄움으로 로컬 부팅 비용 증가 | `dev-up.sh` 가 백그라운드 spawn + healthz polling 으로 부팅 자동화. 개발자는 단일 명령. |
| be-api 의 `/admin/*` 가 외부 노출되면 보안 사고 | 인프라 레벨 차단을 디자인에 명시 (7.1). 로컬은 의도적으로 제한 없음. 배포 체크리스트에 SG 검증 포함. |
| fe/graph.html base URL 분리가 어드민 환경 설정에 의존 | A5 에서 `?api=` 쿼리 + 환경 결정 default 둘 다 지원. README 에 명시. |
| 두 서비스 간 X-Request-ID 추적 부재 | v2. 현재는 디버깅 시 timestamp+엔드포인트 매칭. |

## 13. 결정의 의미 (다시 한 번)

이 디자인은 **인증·캐싱·rate-limit 없이** 출발한다. 즉:
- 로컬 dev 에서 be-api 가 인증 없이 노출됨. **개발자가 잘못 부팅하면 (예: 배포 환경에서 be-api 를 외부 LB 에 매다는 실수) 데이터 노출 위험이 있음.** 인프라 체크리스트와 PR 리뷰가 마지막 방어선.
- 향후 인증을 도입할 때, 도입 위치는 BFF 의 입구 (사용자 인증) 와 be-api 의 입구 (서비스 인증) 두 군데. 본 설계는 두 자리를 비워두지만 hook point 는 명시 (BFF `api.py` 의 `Depends(...)`, be-api `api.py` 의 middleware).

## 14. Next steps

본 디자인 승인 후:
1. `superpowers:writing-plans` 스킬로 SP-A implementation plan 작성. plan 은 sprint A1–A7 단위 TODO + 각 sprint 의 verification 명령 + rollback 절차 명시.
2. SP-B/C (fe Vite + m.html) spec 별도 작성 — SP-A 와 병렬 가능.
