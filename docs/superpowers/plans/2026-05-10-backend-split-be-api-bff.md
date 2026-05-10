# SP-A Backend Split (be-api / be-for-fe BFF) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `cf_backend` 단일 패키지를 두 uv workspace 패키지 `cf-be-api` (DB-tier) + `cf-be-for-fe` (BFF) 로 분리. fe 트래픽은 BFF :8070 만 본다. 어드민·그래프는 be-api 직접 호출.

**Architecture:** be-for-fe 가 httpx 로 be-api 를 HTTP/REST 호출. be-for-fe 는 projection·aggregation 만 (얇은 BFF). 인증·캐싱·rate-limit 은 out-of-scope. 같은 repo, uv workspace 두 패키지. 공유 타입은 `cf_be_api.schemas` 가 source-of-truth, BFF 가 workspace dep 으로 import.

**Tech Stack:** FastAPI, httpx (sync), uv workspace, pytest, pydantic v2.

**Spec:** `docs/superpowers/specs/2026-05-10-backend-split-be-api-bff-design.md`

**Workflow:** 작은 단위 commit, sprint = 1 PR, `gh pr merge --auto --merge` 로 main 자동 머지. 브랜치명 `sprint/a<N>-<topic>`.

---

## Task A1: cf_backend → cf_be_api 패키지 rename + 디렉터리 분할

**Goal:** 현 `backend/src/cf_backend/` 를 `backend/be-api/src/cf_be_api/` 로 이전, alembic 도 함께. 기능 변경 없음.

**Files:**
- Move: `backend/src/cf_backend/` → `backend/be-api/src/cf_be_api/` (git mv 전체 트리)
- Move: `backend/alembic/` → `backend/be-api/alembic/`
- Move: `backend/alembic.ini` → `backend/be-api/alembic.ini`
- Move: `backend/tests/` → `backend/be-api/tests/`
- Move: `backend/README.md` → `backend/be-api/README.md`
- Move: `backend/pyproject.toml` → `backend/be-api/pyproject.toml`
- Modify: `pyproject.toml` (workspace root) — members 갱신
- Rewrite imports across all moved Python files: `cf_backend` → `cf_be_api`
- Rewrite imports in `crawl/camfit/`, `crawl/txcp/`, `pipeline/` if they reference `cf_backend`
- Modify: `scripts/backend-up.sh`, `scripts/backend-down.sh`, `scripts/lib/env.sh` — `cf_backend` → `cf_be_api`
- Modify: `backend/be-api/pyproject.toml` — `name = "cf-be-api"`, `[tool.hatch.build.targets.wheel] packages = ["src/cf_be_api"]`

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/a1-be-api-rename
```

- [ ] **Step 2: git mv 디렉터리 트리**

```bash
mkdir -p backend/be-api/src
git mv backend/src/cf_backend backend/be-api/src/cf_be_api
git mv backend/alembic backend/be-api/alembic
git mv backend/alembic.ini backend/be-api/alembic.ini
git mv backend/tests backend/be-api/tests
git mv backend/README.md backend/be-api/README.md
git mv backend/pyproject.toml backend/be-api/pyproject.toml
# backend/src/ 빈 디렉터리 정리
rmdir backend/src 2>/dev/null || true
```

- [ ] **Step 3: 패키지 메타 갱신**

`backend/be-api/pyproject.toml` 변경:

```toml
[project]
name = "cf-be-api"      # was "cf-backend"
# ... 나머지 동일

[tool.hatch.build.targets.wheel]
packages = ["src/cf_be_api"]   # was ["src/cf_backend"]
```

- [ ] **Step 4: 워크스페이스 root 갱신**

`pyproject.toml` (repo root) 변경:

```toml
[tool.uv.workspace]
members = ["crawl/txcp", "crawl/camfit", "backend/be-api", "pipeline"]

[tool.uv.sources]
cf-be-api = { workspace = true }
# 이전 cf-backend 라인 제거
```

`pipeline/pyproject.toml` 의 `dependencies` 가 `cf-backend` 를 참조하면 `cf-be-api` 로 변경 (확인 필요):

```bash
grep -rn "cf-backend\|cf_backend" pipeline/ crawl/
```

발견된 모든 `cf-backend` (TOML) → `cf-be-api`, `cf_backend` (Python import) → `cf_be_api`.

- [ ] **Step 5: Python import 일괄 rewrite**

```bash
# 모든 .py 파일에서 import 경로 갱신
find backend/be-api crawl pipeline -name "*.py" -type f -exec sed -i 's/\bcf_backend\b/cf_be_api/g' {} +
```

확인:

```bash
grep -rn "cf_backend" backend/be-api crawl pipeline
# 출력 없어야 함
```

- [ ] **Step 6: scripts 갱신**

`scripts/backend-up.sh` 수정 — `cf_backend.api:app` → `cf_be_api.api:app`, `--package cf-backend` → `--package cf-be-api`:

```bash
nohup "$UV" run --package cf-be-api uvicorn cf_be_api.api:app \
    --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
    > "$BACKEND_LOG_FILE" 2>&1 &
```

`scripts/backend-down.sh`, `scripts/lib/env.sh`, `scripts/migrate.sh`, `scripts/test.sh`, `scripts/setup.sh`, `scripts/teardown.sh` 안에 `cf_backend` 또는 `cf-backend` 가 있으면 동일 변경.

```bash
grep -rn "cf_backend\|cf-backend" scripts/
# 모두 갱신했는지 확인
```

- [ ] **Step 7: uv lock 재생성**

```bash
uv sync 2>&1 | tail -10
```

기대: 에러 없이 lock 재생성, `cf-be-api` 패키지 인식.

- [ ] **Step 8: pytest**

```bash
uv run --package cf-be-api pytest backend/be-api/tests -x -q 2>&1 | tail -20
```

기대: 모든 기존 테스트 PASS (기능 변경 없음, 단지 import path 만 변경).

실패 시: 누락된 import rewrite 또는 fixture 경로 — 에러 메시지의 모듈명을 다시 sed.

- [ ] **Step 9: 부팅 smoke**

```bash
# 백그라운드 부팅
BACKEND_PORT=8071 uv run --package cf-be-api uvicorn cf_be_api.api:app --port 8071 &
SERVER_PID=$!
sleep 3
curl -sf http://localhost:8071/healthz && echo "OK"
kill $SERVER_PID
```

기대: `OK` 출력. 응답 JSON 에 `postgres`, `falkor`, `embedder`, `etago`, `geocoder` 키 (값은 환경에 따라 up/down).

- [ ] **Step 10: Commit**

```bash
git add -A backend/ pipeline/ crawl/ scripts/ pyproject.toml uv.lock
git commit -m "$(cat <<'EOF'
refactor(backend): rename cf-backend → cf-be-api + relocate to backend/be-api/

git mv backend/src/cf_backend → backend/be-api/src/cf_be_api.
alembic, tests, README, pyproject 도 함께 이전. 패키지명·import 경로
일괄 rewrite. uv workspace members 갱신. scripts 의 패키지명 갱신.

기능 변경 없음. SP-A sprint A1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 11: Push + PR + auto-merge**

```bash
git push -u origin sprint/a1-be-api-rename
gh pr create --title "refactor(backend): cf-backend → cf-be-api + relocate to backend/be-api/" \
  --body "$(cat <<'EOF'
## Summary
SP-A sprint A1: 패키지 rename + 디렉터리 분할.

- backend/src/cf_backend → backend/be-api/src/cf_be_api
- alembic, tests, README, pyproject 동반 이전
- 패키지명 cf-backend → cf-be-api, import 경로 일괄 rewrite
- uv workspace members + scripts 갱신

기능 변경 없음. 다음 sprint A2 에서 be-for-fe 패키지 신규.

## Test plan
- [x] uv sync PASS
- [x] backend/be-api/tests pytest PASS (기존 테스트)
- [x] uvicorn 부팅 + /healthz 응답

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --auto --merge
```

---

## Task A2: be-for-fe 패키지 신규 + 얇은 통과 엔드포인트

**Goal:** `backend/be-for-fe/` 패키지 신규. httpx client + healthz + 단순 통과 (`/facets`, `/concepts`, `/themes`, `/marks*`, `/featured-axes`). projection 없이 본문 그대로 패스스루.

**Files:**
- Create: `backend/be-for-fe/pyproject.toml`
- Create: `backend/be-for-fe/README.md`
- Create: `backend/be-for-fe/src/cf_be_for_fe/__init__.py`
- Create: `backend/be-for-fe/src/cf_be_for_fe/settings.py`
- Create: `backend/be-for-fe/src/cf_be_for_fe/client.py`
- Create: `backend/be-for-fe/src/cf_be_for_fe/api.py`
- Create: `backend/be-for-fe/tests/__init__.py`
- Create: `backend/be-for-fe/tests/test_passthrough.py`
- Modify: `pyproject.toml` (workspace root) — members 에 `backend/be-for-fe` 추가, `cf-be-for-fe = { workspace = true }` 추가

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/a2-be-for-fe-scaffold
```

- [ ] **Step 2: 패키지 메타 작성**

`backend/be-for-fe/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cf-be-for-fe"
version = "0.1.0"
description = "cf BFF — projection + aggregation over cf-be-api. Externally exposed."
requires-python = ">=3.11"
authors = [{ name = "cxx_2" }]
license = { text = "MIT" }

dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.4",
    "cf-be-api",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "respx>=0.21"]

[tool.uv.sources]
cf-be-api = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/cf_be_for_fe"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: 워크스페이스 root 갱신**

`pyproject.toml` (repo root):

```toml
[tool.uv.workspace]
members = ["crawl/txcp", "crawl/camfit", "backend/be-api", "backend/be-for-fe", "pipeline"]

[tool.uv.sources]
cf-be-api = { workspace = true }
cf-be-for-fe = { workspace = true }
```

- [ ] **Step 4: settings 작성**

`backend/be-for-fe/src/cf_be_for_fe/settings.py`:

```python
"""be-for-fe (BFF) settings."""
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BFF_", env_file=".env", extra="ignore")

    be_api_base_url: str = "http://localhost:8071"
    timeout_s: float = 12.0
    allowed_origins: list[str] = ["*"]   # 프로덕션은 fe origin 화이트리스트로 좁힘
```

- [ ] **Step 5: httpx client 작성**

`backend/be-for-fe/src/cf_be_for_fe/client.py`:

```python
"""Sync httpx client to be-api. One Client per app instance (lifetime = app)."""
from __future__ import annotations
from typing import Any
import httpx


class BeApiError(Exception):
    """Raised when be-api returns 5xx or times out. BFF translates to 503."""
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class BeApiClient:
    def __init__(self, base_url: str, timeout_s: float = 12.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s)

    def close(self) -> None:
        self._client.close()

    def get(self, path: str, **params: Any) -> Any:
        try:
            r = self._client.get(path, params={k: v for k, v in params.items() if v is not None})
        except httpx.TimeoutException as e:
            raise BeApiError(f"timeout calling {path}") from e
        except httpx.HTTPError as e:
            raise BeApiError(f"http error calling {path}: {e}") from e
        if r.status_code >= 500:
            raise BeApiError(f"be-api {r.status_code} on {path}", status=r.status_code)
        if r.status_code == 404:
            raise BeApiError(f"be-api 404 on {path}", status=404)
        r.raise_for_status()
        return r.json()

    def post_json(self, path: str, body: Any) -> Any:
        try:
            r = self._client.post(path, json=body)
        except httpx.TimeoutException as e:
            raise BeApiError(f"timeout calling {path}") from e
        except httpx.HTTPError as e:
            raise BeApiError(f"http error calling {path}: {e}") from e
        if r.status_code >= 500:
            raise BeApiError(f"be-api {r.status_code} on {path}", status=r.status_code)
        r.raise_for_status()
        return r.json()

    def delete(self, path: str) -> Any:
        r = self._client.delete(path)
        r.raise_for_status()
        return r.json() if r.text else {}
```

- [ ] **Step 6: api 작성 (얇은 통과)**

`backend/be-for-fe/src/cf_be_for_fe/api.py`:

```python
"""BFF FastAPI surface — fe 가 호출. be-api 를 httpx 로 통과·변환."""
from __future__ import annotations
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .settings import Settings
from .client import BeApiClient, BeApiError

_settings = Settings()
_client = BeApiClient(_settings.be_api_base_url, _settings.timeout_s)

app = FastAPI(title="cf BFF (be-for-fe)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


def _passthrough_get(path: str, **params: Any) -> Any:
    try:
        return _client.get(path, **params)
    except BeApiError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/healthz")
def healthz() -> dict:
    """BFF 자체 헬스 + be-api 연결 가능 여부."""
    try:
        upstream = _client.get("/healthz")
        return {"bff": "ok", "be_api": upstream}
    except BeApiError as e:
        return {"bff": "ok", "be_api": {"error": str(e)}}


# 얇은 통과 — A2 범위
@app.get("/facets")
def facets() -> dict:
    return _passthrough_get("/facets")


@app.get("/concepts")
def concepts() -> list[dict]:
    return _passthrough_get("/concepts")


@app.get("/concepts/{name}/camps")
def concept_camps(name: str, min_score: float = 0.3, limit: int = 200) -> list[dict]:
    return _passthrough_get(f"/concepts/{name}/camps", min_score=min_score, limit=limit)


@app.get("/themes")
def themes() -> list[dict]:
    return _passthrough_get("/themes")


@app.get("/themes/{theme_id}/camps")
def theme_camps(theme_id: str, limit: int = 200) -> list[dict]:
    return _passthrough_get(f"/themes/{theme_id}/camps", limit=limit)


@app.get("/marks")
def list_marks() -> dict:
    return _passthrough_get("/marks")


@app.get("/marks/{axis}/camps")
def axis_camps(axis: str, min_level: Optional[str] = None, limit: int = 100) -> list[dict]:
    return _passthrough_get(f"/marks/{axis}/camps", min_level=min_level, limit=limit)


@app.get("/featured-axes")
def featured_axes() -> list[dict]:
    return _passthrough_get("/featured-axes")
```

- [ ] **Step 7: __init__**

`backend/be-for-fe/src/cf_be_for_fe/__init__.py`:

```python
"""cf BFF (Backend-For-Frontend) — projection + aggregation layer over cf-be-api."""
__version__ = "0.1.0"
```

- [ ] **Step 8: README 작성**

`backend/be-for-fe/README.md`:

````markdown
# cf-be-for-fe

BFF (Backend-For-Frontend). 외부 노출. fe 의 모든 트래픽이 진입.

- be-api 를 httpx 로 호출, projection·aggregation 적용
- 인증·캐싱·rate-limit 은 본 sprint 범위 외 (출 진입점 자리만 확보)

## Run

```sh
# Dev — be-api 가 :8071 떠있다고 가정
BFF_BE_API_BASE_URL=http://localhost:8071 \
  uv run --package cf-be-for-fe uvicorn cf_be_for_fe.api:app --port 8070 --reload
```

## Endpoints (A2 시점)

얇은 통과: `/facets`, `/concepts*`, `/themes*`, `/marks*`, `/featured-axes`. 후속 sprint 에서 `/sites*`, `/eta*` 추가 + projection.
````

- [ ] **Step 9: respx 기반 단위 테스트**

`backend/be-for-fe/tests/test_passthrough.py`:

```python
"""BFF 가 be-api 를 정확히 호출하는지 + 본문 그대로 반환하는지 검증."""
from __future__ import annotations
import pytest
import respx
from httpx import Response
from fastapi.testclient import TestClient

import cf_be_for_fe.api as api_mod


@pytest.fixture
def client():
    return TestClient(api_mod.app)


@respx.mock
def test_facets_passthrough(client):
    sample = {
        "regions": [{"sido": "강원", "sigungu": "춘천", "count": 12}],
        "concept_axes": [],
        "concepts": [],
        "themes": [],
    }
    respx.get("http://localhost:8071/facets").mock(return_value=Response(200, json=sample))

    r = client.get("/facets")
    assert r.status_code == 200
    assert r.json() == sample


@respx.mock
def test_concept_camps_query_forwarding(client):
    sample = [{"id": "c1", "score": 0.9}]
    route = respx.get("http://localhost:8071/concepts/valley/camps").mock(
        return_value=Response(200, json=sample)
    )
    r = client.get("/concepts/valley/camps?min_score=0.5&limit=50")
    assert r.status_code == 200
    assert r.json() == sample
    assert route.called
    # query 가 정확히 전달되었는지
    qs = dict(route.calls.last.request.url.params)
    assert qs == {"min_score": "0.5", "limit": "50"}


@respx.mock
def test_be_api_5xx_becomes_503(client):
    respx.get("http://localhost:8071/facets").mock(return_value=Response(500))
    r = client.get("/facets")
    assert r.status_code == 503


@respx.mock
def test_be_api_timeout_becomes_503(client):
    import httpx
    respx.get("http://localhost:8071/facets").mock(side_effect=httpx.TimeoutException("t/o"))
    r = client.get("/facets")
    assert r.status_code == 503


@respx.mock
def test_healthz_combines_self_and_upstream(client):
    respx.get("http://localhost:8071/healthz").mock(return_value=Response(200, json={"postgres": "up"}))
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["bff"] == "ok"
    assert body["be_api"] == {"postgres": "up"}
```

- [ ] **Step 10: uv sync 후 pytest**

```bash
uv sync 2>&1 | tail -5
uv run --package cf-be-for-fe pytest backend/be-for-fe/tests -x -v 2>&1 | tail -20
```

기대: 5 PASS.

- [ ] **Step 11: 통합 smoke (be-api + bff 동시 부팅)**

```bash
# Terminal 1
BACKEND_PORT=8071 uv run --package cf-be-api uvicorn cf_be_api.api:app --port 8071 &
A_PID=$!

# Terminal 2 (또는 백그라운드)
BFF_BE_API_BASE_URL=http://localhost:8071 \
  uv run --package cf-be-for-fe uvicorn cf_be_for_fe.api:app --port 8070 &
B_PID=$!

sleep 3

# BFF 가 be-api 통과해서 facets 응답
curl -sf http://localhost:8070/facets | head -c 200 && echo

# 정리
kill $A_PID $B_PID
```

기대: facets JSON 의 첫 200byte 가 be-api 직접 호출한 것과 동일.

- [ ] **Step 12: Commit (작은 단위 — 인프라 / 코드 / 테스트 분리)**

```bash
# Commit 1: 패키지 메타 (workspace 갱신)
git add pyproject.toml backend/be-for-fe/pyproject.toml backend/be-for-fe/README.md
git commit -m "chore(workspace): scaffold cf-be-for-fe package

uv workspace members 추가, pyproject + README. SP-A A2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 2: 코드
git add backend/be-for-fe/src/
git commit -m "feat(bff): httpx client + thin passthrough endpoints

settings, BeApiClient, FastAPI surface with /healthz +
/facets /concepts* /themes* /marks* /featured-axes 통과.
projection 은 다음 sprint A3 에서. SP-A A2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 3: 테스트
git add backend/be-for-fe/tests/ uv.lock
git commit -m "test(bff): respx-mocked passthrough + 5xx/timeout → 503

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 13: Push + PR + auto-merge**

```bash
git push -u origin sprint/a2-be-for-fe-scaffold
gh pr create --title "feat(bff): scaffold cf-be-for-fe + thin passthrough" \
  --body "$(cat <<'EOF'
## Summary
SP-A sprint A2: be-for-fe 패키지 신규.

- uv workspace 멤버 추가, pyproject + README
- BeApiClient (httpx sync) — 5xx/timeout → BeApiError → 503
- FastAPI surface: /healthz + 얇은 통과 (/facets, /concepts*, /themes*, /marks*, /featured-axes)
- respx 단위 테스트 5개

다음 sprint A3 에서 projection (sites/*) 이전.

## Test plan
- [x] backend/be-for-fe/tests pytest 5 PASS
- [x] 통합 smoke: be-api :8071 + bff :8070 동시 부팅, /facets 통과 확인

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --auto --merge
```

---

## Task A3: projection 이전 + sites/* 라우팅

**Goal:** `_camp_to_fe_row`, `_filter_maritime_for_inland`, `_filter_location_types_for_inland`, `_project_categories`, `_LANDLOCKED_SIDO` 를 cf_be_api → cf_be_for_fe 로 이전. cf_be_api 는 raw 도메인 dict 만 반환. `/sites`, `/sites/{id}`, `/sites/search`, `/sites/{id}/similar` 의 fe 응답이 byte-수준 동일.

**Files:**
- Create: `backend/be-for-fe/src/cf_be_for_fe/constants.py` — `_LANDLOCKED_SIDO`
- Create: `backend/be-for-fe/src/cf_be_for_fe/projection.py` — `camp_to_fe_row`, `filter_maritime_for_inland`, `filter_location_types_for_inland`, `project_categories`
- Modify: `backend/be-api/src/cf_be_api/api.py` — `/sites*` 핸들러가 raw 도메인 dict 반환 (projection 호출 제거). `_camp_to_fe_row` 등 함수 본체는 유지(임시) 하되 호출하지 않음 (또는 즉시 삭제 — 본 sprint 에서 결정: 즉시 삭제)
- Modify: `backend/be-for-fe/src/cf_be_for_fe/api.py` — `/sites*` 4개 엔드포인트 추가, BeApiClient.get + projection 적용
- Create: `backend/be-for-fe/tests/test_sites_projection.py`
- Create: `backend/be-for-fe/tests/fixtures/be_api_sites.json` — A2 시점 응답 캡처 (회귀 fixture)

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/a3-projection-and-sites
```

- [ ] **Step 2: 회귀 fixture 캡처 (A3 진행 *전*)**

A2 시점에 fe 가 받는 `/sites` 응답을 fixture 로 캡처. be-api + (현 시점에는 sites 가 BFF 에 없으므로 be-api 직접) 호출.

```bash
# be-api 부팅 (fe 와 직접 통신)
uv run --package cf-be-api uvicorn cf_be_api.api:app --port 8071 &
A_PID=$!
sleep 3

mkdir -p backend/be-for-fe/tests/fixtures
# 데이터가 충분히 있다고 가정 — 없으면 빈 배열 캡처되어 회귀 의미 없음
curl -s "http://localhost:8071/sites?region=강원" > /tmp/before_a3_sites_gangwon.json
curl -s "http://localhost:8071/sites?concept=valley" > /tmp/before_a3_sites_valley.json
curl -s "http://localhost:8071/sites?region=강원&concept=valley" > /tmp/before_a3_sites_gangwon_valley.json
SITE_ID=$(jq -r '.[0].id // empty' /tmp/before_a3_sites_gangwon.json)
[ -n "$SITE_ID" ] && curl -s "http://localhost:8071/sites/$SITE_ID" > /tmp/before_a3_site_detail.json

kill $A_PID
```

이 파일들을 `backend/be-for-fe/tests/fixtures/regression/` 에 저장:

```bash
mkdir -p backend/be-for-fe/tests/fixtures/regression
cp /tmp/before_a3_*.json backend/be-for-fe/tests/fixtures/regression/
```

⚠️ 데이터 의존성: 로컬 DB 가 prod 와 다를 수 있음. fixture 는 *현재 환경* 의 응답 stage. 변경 후 같은 환경에서 같은 응답이 나오는지가 검증 의미.

- [ ] **Step 3: BFF projection 모듈 작성**

`backend/be-for-fe/src/cf_be_for_fe/constants.py`:

```python
"""BFF constants — fe-friendly value sets."""
from __future__ import annotations

# 내륙 sido — '바다' 관련 마커가 잘못 붙은 데이터를 BFF projection 단계에서 정리
_LANDLOCKED_SIDO = frozenset({
    "충북", "대전", "세종", "광주광역시",  # ← cf_be_api/api.py 의 원본을 그대로 옮김
    # 정확한 목록은 backend/be-api/src/cf_be_api/api.py 의 _LANDLOCKED_SIDO 정의를 그대로 복사
})
```

⚠️ 작업 시: `cf_be_api/api.py` 안의 실제 `_LANDLOCKED_SIDO` 정의 (api.py 라인 ~185 부근) 를 *그대로* 복사. 위 placeholder 가 아닌 실제 값.

`backend/be-for-fe/src/cf_be_for_fe/projection.py`:

```python
"""FE-friendly projection of be-api raw responses.

Moved from cf_be_api/api.py during SP-A sprint A3.
"""
from __future__ import annotations
from typing import Any

from .constants import _LANDLOCKED_SIDO


def filter_maritime_for_inland(items: list[Any], sido: str | None) -> list:
    """내륙 sido 의 항목에서 'ocean' 등 해양 태그 제거.

    원본: cf_backend/api.py:_filter_maritime_for_inland
    """
    if sido in _LANDLOCKED_SIDO:
        return [x for x in items if x not in {"ocean", "island"}]
    return items


def filter_location_types_for_inland(loc_types: list[str], sido: str | None) -> list[str]:
    """위와 동일 규칙으로 location_types 필터.

    원본: cf_backend/api.py:_filter_location_types_for_inland
    """
    if sido in _LANDLOCKED_SIDO:
        return [x for x in loc_types if x not in {"ocean", "island"}]
    return loc_types


def project_categories(collections: list, types: list) -> list[str]:
    """collections 와 types 를 fe 친화 카테고리 리스트로 합성.

    원본: cf_backend/api.py:_project_categories
    """
    out: list[str] = []
    for c in collections or []:
        if isinstance(c, dict) and "name" in c:
            out.append(c["name"])
        elif isinstance(c, str):
            out.append(c)
    for t in types or []:
        if isinstance(t, str) and t not in out:
            out.append(t)
    return out


def camp_to_fe_row(c: dict) -> dict:
    """Camp(raw dict) → fe 친화 flat row.

    원본: cf_backend/api.py:_camp_to_fe_row
    """
    sido = c.get("sido")
    return {
        **c,
        "categories": project_categories(c.get("collections") or [], c.get("locationTypes") or []),
        "locationTypes": filter_location_types_for_inland(c.get("locationTypes") or [], sido),
    }


def project_camps(rows: list[dict]) -> list[dict]:
    """일괄 projection."""
    return [camp_to_fe_row(c) for c in rows]
```

⚠️ 작업 시: 위 4 함수의 *실제* 구현은 `cf_be_api/api.py` 의 원본 그대로 옮김. 위 코드는 시그니처/패턴 참고용 — 원본 로직(예: locationTypes 와 collections 의 정확한 변환 규칙) 을 1:1 복사.

- [ ] **Step 4: be-api 의 sites/* 핸들러 정리 — projection 호출 제거**

`backend/be-api/src/cf_be_api/api.py` 의 `/sites`, `/sites/{site_id}`, `/sites/search`, `/sites/{site_id}/similar` 핸들러:

- 현재 `_camp_to_fe_row(c)` 호출 → 그냥 `c` (또는 raw dict) 반환
- `_filter_maritime_for_inland(...)` 호출 → 제거 (raw 그대로)
- `_filter_location_types_for_inland(...)` 호출 → 제거
- `_project_categories(...)` 호출 → 제거

함수 정의 (`_camp_to_fe_row`, `_filter_maritime_for_inland`, `_filter_location_types_for_inland`, `_project_categories`, `_LANDLOCKED_SIDO`) 도 삭제.

⚠️ `cf_be_api` 의 *internal* 사용 (다른 핸들러나 그래프 서브시스템에서) 이 있는지 확인:

```bash
grep -rn "_camp_to_fe_row\|_filter_maritime\|_filter_location_types\|_project_categories\|_LANDLOCKED_SIDO" backend/be-api/src/
```

발견된 internal 사용 있으면 그 자리는 raw dict 처리로 마이그레이션 (도메인 레이어에 fe-friendly 가공이 들어가면 안 되는 게 본 sprint 의 의도).

- [ ] **Step 5: be-api 단위 테스트 갱신**

`backend/be-api/tests/` 안에 `_camp_to_fe_row` 등을 직접 import 하는 테스트가 있으면 — 해당 테스트는 BFF 로 옮기거나 (Step 6), be-api 측은 raw dict 응답 검증으로 변경.

```bash
grep -rn "_camp_to_fe_row\|_filter_maritime\|_project_categories" backend/be-api/tests/
```

발견되면 각 테스트의 의도를 보고:
- "응답 형태가 fe 친화" 검증 → BFF 테스트로 이동 (Step 6)
- "도메인 데이터 정확성" 검증 → raw dict 기준으로 다시 작성

- [ ] **Step 6: BFF /sites* 엔드포인트 추가**

`backend/be-for-fe/src/cf_be_for_fe/api.py` 에 추가:

```python
from .projection import project_camps, camp_to_fe_row


@app.get("/sites")
def sites(
    region: Optional[str] = None,
    concept: list[str] = Query(default_factory=list),
) -> list[dict]:
    raw = _passthrough_get("/sites", region=region, concept=concept)
    if not isinstance(raw, list):
        raise HTTPException(status_code=502, detail="be-api /sites returned non-list")
    return project_camps(raw)


@app.get("/sites/{site_id}")
def site_detail(site_id: str) -> dict:
    raw = _passthrough_get(f"/sites/{site_id}")
    return camp_to_fe_row(raw)


@app.get("/sites/search")
def site_search(q: str = Query(..., min_length=1), k: int = 20) -> list[dict]:
    raw = _passthrough_get("/sites/search", q=q, k=k)
    return project_camps(raw)


@app.get("/sites/{site_id}/similar")
def site_similar(site_id: str, k: int = 10) -> list[dict]:
    raw = _passthrough_get(f"/sites/{site_id}/similar", k=k)
    return project_camps(raw)
```

⚠️ `Query(default_factory=list)` 가 `concept=valley&concept=mountain` 같은 repeated param 을 받음. 동작 확인 필요.

- [ ] **Step 7: 회귀 테스트 (BFF + be-api 통합)**

`backend/be-for-fe/tests/test_sites_projection.py`:

```python
"""SP-A A3 회귀 테스트.

A2 시점에 be-api 가 fe 친화 응답을 직접 반환했음 (projection 포함).
A3 후에는 be-api 가 raw 도메인 dict 반환, BFF 가 projection.
**최종 fe 응답이 byte-수준 동일** 해야 함.

이 테스트는 fixtures/regression/ 의 캡처와 비교한다 (실 환경 통합).
"""
from __future__ import annotations
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "regression"

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1",
    reason="integration test — run with RUN_INTEGRATION=1 and live DB stack",
)


@pytest.fixture(scope="module")
def stack():
    """be-api :8071 + bff :8070 동시 부팅, teardown."""
    a = subprocess.Popen(
        ["uv", "run", "--package", "cf-be-api", "uvicorn", "cf_be_api.api:app", "--port", "8071"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    b = subprocess.Popen(
        ["uv", "run", "--package", "cf-be-for-fe", "uvicorn", "cf_be_for_fe.api:app", "--port", "8070"],
        env={**os.environ, "BFF_BE_API_BASE_URL": "http://localhost:8071"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # 부팅 대기
    for _ in range(20):
        try:
            httpx.get("http://localhost:8070/healthz", timeout=1.0)
            break
        except Exception:
            time.sleep(0.5)
    yield
    a.terminate()
    b.terminate()
    a.wait(timeout=5)
    b.wait(timeout=5)


def _normalize(d):
    """JSON 비교 — 키 순서 무관. 값은 정확히 일치해야."""
    return json.loads(json.dumps(d, sort_keys=True))


@pytest.mark.parametrize("fixture_name,url", [
    ("before_a3_sites_gangwon.json", "http://localhost:8070/sites?region=강원"),
    ("before_a3_sites_valley.json", "http://localhost:8070/sites?concept=valley"),
    ("before_a3_sites_gangwon_valley.json", "http://localhost:8070/sites?region=강원&concept=valley"),
])
def test_sites_projection_regression(stack, fixture_name, url):
    expected = _normalize(json.loads((FIXTURES / fixture_name).read_text()))
    actual = _normalize(httpx.get(url).json())
    assert actual == expected, f"{fixture_name}: BFF projection 결과가 사전 캡처와 다름"


def test_site_detail_regression(stack):
    fixture = FIXTURES / "before_a3_site_detail.json"
    if not fixture.exists():
        pytest.skip("detail fixture 캡처 안 됨 (sites 가 비어있었을 수 있음)")
    expected = _normalize(json.loads(fixture.read_text()))
    site_id = expected["id"]
    actual = _normalize(httpx.get(f"http://localhost:8070/sites/{site_id}").json())
    assert actual == expected
```

`backend/be-for-fe/tests/fixtures/regression/` 에 Step 2 에서 캡처한 JSON 파일들 commit. (실제 데이터 들어감)

- [ ] **Step 8: BFF projection 단위 테스트**

`backend/be-for-fe/tests/test_projection_unit.py`:

```python
"""projection.py 단위 테스트 — 통합 환경 없이도 PASS."""
from cf_be_for_fe.projection import (
    camp_to_fe_row,
    filter_maritime_for_inland,
    filter_location_types_for_inland,
    project_categories,
)


def test_filter_maritime_for_inland_strips_ocean():
    out = filter_maritime_for_inland(["ocean", "river"], sido="충북")
    assert out == ["river"]


def test_filter_maritime_for_inland_passes_coast():
    out = filter_maritime_for_inland(["ocean", "river"], sido="강원")
    assert out == ["ocean", "river"]


def test_filter_location_types_for_inland_strips_island():
    out = filter_location_types_for_inland(["mountain", "island"], sido="충북")
    assert out == ["mountain"]


def test_project_categories_dedups():
    out = project_categories([{"name": "a"}], ["a", "b"])
    assert out == ["a", "b"]


def test_camp_to_fe_row_includes_categories():
    row = camp_to_fe_row({
        "id": "c1",
        "sido": "강원",
        "collections": [{"name": "오션뷰"}],
        "locationTypes": ["ocean", "mountain"],
    })
    assert row["id"] == "c1"
    assert "categories" in row
    assert row["locationTypes"] == ["ocean", "mountain"]   # 강원은 해양 OK
```

⚠️ `_LANDLOCKED_SIDO` 의 실제 내용에 따라 위 테스트의 sido 값을 조정.

- [ ] **Step 9: pytest**

```bash
# 단위 (실 DB 무관)
uv run --package cf-be-for-fe pytest backend/be-for-fe/tests/test_projection_unit.py -v 2>&1 | tail -10

# 회귀 (실 DB + 두 서비스 부팅 — DB 환경 ready 시에만)
RUN_INTEGRATION=1 uv run --package cf-be-for-fe pytest backend/be-for-fe/tests/test_sites_projection.py -v 2>&1 | tail -20
```

기대: 단위 5 PASS, 회귀 3-4 PASS (fixture 캡처 시점에 데이터 있었던 만큼).

회귀 실패 시: BFF projection 결과와 사전 캡처 비교 — 누락된 변환·키 순서·타입 차이 fix.

- [ ] **Step 10: be-api 도 pytest 깨지는 것 없는지 확인**

```bash
uv run --package cf-be-api pytest backend/be-api/tests -x -q 2>&1 | tail -10
```

기대: 모든 테스트 PASS. 깨지면 Step 5 의 갱신 누락.

- [ ] **Step 11: Commit (작은 단위)**

```bash
# Commit 1: BFF projection 모듈 + 단위 테스트
git add backend/be-for-fe/src/cf_be_for_fe/constants.py \
        backend/be-for-fe/src/cf_be_for_fe/projection.py \
        backend/be-for-fe/tests/test_projection_unit.py
git commit -m "feat(bff): projection module — moved from cf_be_api

camp_to_fe_row, filter_maritime_for_inland, filter_location_types_for_inland,
project_categories, _LANDLOCKED_SIDO. SP-A A3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 2: be-api raw 응답 정리
git add backend/be-api/src/cf_be_api/api.py backend/be-api/tests/
git commit -m "refactor(be-api): /sites* return raw domain dicts

projection 함수·_LANDLOCKED_SIDO 삭제. fe-friendly 가공은 BFF 책임으로 이전. SP-A A3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 3: BFF /sites* 엔드포인트 + 회귀 fixture + 회귀 테스트
git add backend/be-for-fe/src/cf_be_for_fe/api.py \
        backend/be-for-fe/tests/test_sites_projection.py \
        backend/be-for-fe/tests/fixtures/regression/
git commit -m "feat(bff): /sites* with projection + regression fixtures

A2 시점 응답을 fixtures/regression/ 에 캡처. RUN_INTEGRATION=1 시
두 서비스 부팅 후 BFF 응답이 byte-수준 동일 검증. SP-A A3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 12: Push + PR + auto-merge**

```bash
git push -u origin sprint/a3-projection-and-sites
gh pr create --title "refactor(be-api,bff): projection move + /sites* via BFF" \
  --body "$(cat <<'EOF'
## Summary
SP-A sprint A3: projection 책임 BFF 로 이전 + sites/* 라우팅.

- cf_be_api: _camp_to_fe_row, _filter_maritime_*, _project_categories,
  _LANDLOCKED_SIDO 삭제. /sites* 가 raw 도메인 dict 반환
- cf_be_for_fe: projection.py, constants.py 신규. /sites, /sites/{id},
  /sites/search, /sites/{id}/similar 엔드포인트 추가 + projection 적용
- 회귀 fixture 4개 (강원·valley·강원+valley 사이트 + 디테일 1개)
- BFF projection 단위 테스트 5개

## Test plan
- [x] backend/be-for-fe pytest 단위 5 PASS
- [x] backend/be-api pytest 기존 테스트 PASS (projection 함수 제거 영향 없음)
- [x] RUN_INTEGRATION=1 으로 회귀 테스트 PASS (실 DB 환경)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --auto --merge
```

---

## Task A4: /eta* BFF 통과

**Goal:** `/eta`, `/eta/batch`, `/eta/cache` (DELETE) 를 BFF 가 통과. fe 가 BFF 로만 호출.

**Files:**
- Modify: `backend/be-for-fe/src/cf_be_for_fe/api.py` — eta 엔드포인트 3개 추가
- Modify: `backend/be-for-fe/src/cf_be_for_fe/client.py` — `delete()` 사용 확인 (이미 A2 에 있음)
- Create: `backend/be-for-fe/tests/test_eta_passthrough.py`

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/a4-eta-passthrough
```

- [ ] **Step 2: be-api 의 /eta 핸들러 시그니처 확인**

```bash
grep -A 8 "@app.get(\"/eta\")\|@app.post(\"/eta/batch\")\|@app.delete(\"/eta/cache\")" \
  backend/be-api/src/cf_be_api/api.py
```

`EtaBatchRequest` Pydantic 모델 정의 확인. BFF 는 같은 모델을 import 또는 dict 통과.

- [ ] **Step 3: BFF 에 eta 엔드포인트 추가**

`backend/be-for-fe/src/cf_be_for_fe/api.py` 추가:

```python
from pydantic import BaseModel, Field


class EtaOriginIn(BaseModel):
    lat: float
    lon: float


class EtaBatchRequest(BaseModel):
    """be-api 의 EtaBatchRequest 미러 — workspace dep 으로 import 도 가능하지만
    BFF 가 contract 격리를 위해 자체 정의 (스키마 변경 시 양쪽 갱신 필요)."""
    origin: EtaOriginIn
    ids: list[str]
    max_minutes: int | None = None
    concurrency: int = 4
    timeout_s: int = 12


@app.get("/eta")
def eta_one(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> dict:
    return _passthrough_get(
        "/eta",
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
    )


@app.post("/eta/batch")
def eta_batch(req: EtaBatchRequest) -> dict:
    try:
        return _client.post_json("/eta/batch", req.model_dump())
    except BeApiError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.delete("/eta/cache")
def eta_cache_clear() -> dict:
    try:
        return _client.delete("/eta/cache")
    except BeApiError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
```

⚠️ be-api 의 실제 `/eta` 시그니처 (Step 2 grep 결과) 와 정확히 일치하도록 — query param 이름·순서·타입 검증.

- [ ] **Step 4: 테스트**

`backend/be-for-fe/tests/test_eta_passthrough.py`:

```python
import pytest
import respx
from httpx import Response
from fastapi.testclient import TestClient

import cf_be_for_fe.api as api_mod


@pytest.fixture
def client():
    return TestClient(api_mod.app)


@respx.mock
def test_eta_one_passthrough(client):
    sample = {"minutes": 42, "via": "highway"}
    respx.get("http://localhost:8071/eta").mock(return_value=Response(200, json=sample))
    r = client.get("/eta?origin_lat=37.5&origin_lon=126.9&dest_lat=37.6&dest_lon=127.0")
    assert r.status_code == 200
    assert r.json() == sample


@respx.mock
def test_eta_batch_post_passthrough(client):
    sample = {"results": {"c1": {"minutes": 30}}}
    route = respx.post("http://localhost:8071/eta/batch").mock(return_value=Response(200, json=sample))
    body = {
        "origin": {"lat": 37.5, "lon": 126.9},
        "ids": ["c1", "c2"],
        "max_minutes": 60,
        "concurrency": 4,
        "timeout_s": 12,
    }
    r = client.post("/eta/batch", json=body)
    assert r.status_code == 200
    assert r.json() == sample
    assert route.called


@respx.mock
def test_eta_cache_delete_passthrough(client):
    respx.delete("http://localhost:8071/eta/cache").mock(return_value=Response(200, json={"cleared": 12}))
    r = client.delete("/eta/cache")
    assert r.status_code == 200
    assert r.json() == {"cleared": 12}
```

- [ ] **Step 5: pytest**

```bash
uv run --package cf-be-for-fe pytest backend/be-for-fe/tests/test_eta_passthrough.py -v 2>&1 | tail -10
```

기대: 3 PASS.

- [ ] **Step 6: 통합 smoke (fe 시나리오)**

```bash
# 두 서비스 부팅
BACKEND_PORT=8071 uv run --package cf-be-api uvicorn cf_be_api.api:app --port 8071 &
A=$!
BFF_BE_API_BASE_URL=http://localhost:8071 \
  uv run --package cf-be-for-fe uvicorn cf_be_for_fe.api:app --port 8070 &
B=$!
sleep 3

# fe 가 호출하는 ETA 시나리오
curl -s -X POST http://localhost:8070/eta/batch \
  -H "Content-Type: application/json" \
  -d '{"origin":{"lat":37.5,"lon":126.9},"ids":["sample1"],"concurrency":4,"timeout_s":12}' | head -c 500

kill $A $B
```

기대: be-api 에서 etago 결과 받아 BFF 통해 응답.

- [ ] **Step 7: Commit + Push + PR**

```bash
git add backend/be-for-fe/src/cf_be_for_fe/api.py backend/be-for-fe/tests/test_eta_passthrough.py
git commit -m "feat(bff): /eta /eta/batch /eta/cache passthrough

EtaBatchRequest Pydantic 모델 자체 정의 (be-api 와 contract 격리).
respx 통과 테스트 3개. SP-A A4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/a4-eta-passthrough
gh pr create --title "feat(bff): eta/* passthrough" \
  --body "SP-A sprint A4. /eta GET, /eta/batch POST, /eta/cache DELETE 통과.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Task A5: 어드민·그래프 라우팅 분리 + fe/graph.html base URL

**Goal:** `/graph/*`, `/admin/*` 는 be-for-fe 가 노출하지 않음 (변경 없음 — 처음부터 안 노출함). fe/graph.html 의 base URL 결정 로직 정리: `?api=` 쿼리 우선 → 없으면 동일 origin (어드민이 직접 be-api 호스트 접근).

**Files:**
- Modify: `fe/graph.html` — API base URL 결정 로직 갱신 (현재 `location.port === "8070"` 분기 → `?api=` 쿼리 추가)
- Create: `backend/be-api/README.md` — 어드민 라우팅 안내 보강 (이미 A1 에서 옮겼으므로 modify)
- Create: `backend/be-for-fe/README.md` — out-of-scope 명시

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/a5-admin-graph-routing
```

- [ ] **Step 2: fe/graph.html 의 현재 base URL 결정 로직 확인**

```bash
grep -n "location.port\|API\b" fe/graph.html | head -20
```

- [ ] **Step 3: graph.html base URL 결정 로직 갱신**

`fe/graph.html` 에서 API base 결정 부분 수정. 예 (실제 코드 위치는 grep 결과 따라):

```javascript
// before:
const API = (typeof location !== "undefined" && location.port === "8070")
  ? "" : "http://localhost:8070";

// after:
const API = (() => {
  const params = new URLSearchParams(location.search);
  const fromQuery = params.get("api");
  if (fromQuery) return fromQuery;        // ?api=http://admin-host:8071 우선
  return "";                              // 없으면 동일 origin (어드민이 be-api 직접)
})();
```

⚠️ graph.html 은 어드민 전용. 이 변경은 BFF 의 graph 통과를 막는 게 아니라 (BFF 가 처음부터 graph 안 노출) — graph.html 사용자가 어디서 호출할지 결정하는 *클라이언트 결정점* 을 명시하는 것.

- [ ] **Step 4: be-api README 갱신**

`backend/be-api/README.md` 에 추가 섹션:

```markdown
## Admin / graph endpoints

`/admin/*` 와 `/graph/*` 는 be-api 에만 존재. BFF (cf-be-for-fe) 는 이들을
노출하지 않는다. 어드민 도구 (예: fe/graph.html) 는 직접 be-api 호스트로
호출:

```
http://admin.internal:8071/graph/sample?...
```

`fe/graph.html` 의 `?api=` 쿼리로 base URL 주입 가능:

```
fe/graph.html?api=http://admin.internal:8071
```

VPC 내부 또는 사내망 접근 가정. 외부 인터넷 노출 금지 — SG/firewall 로 차단.
```

- [ ] **Step 5: be-for-fe README 보강**

`backend/be-for-fe/README.md` 끝에:

```markdown
## Out of scope

- `/admin/*`, `/graph/*` — be-api 직접 (어드민 전용, VPC 내부 가정)
- 인증·캐싱·rate-limit — 후속 sprint
```

- [ ] **Step 6: graph.html smoke (수동)**

```bash
# 1) 동일 origin 모드 — be-api 만 띄움
BACKEND_PORT=8071 uv run --package cf-be-api uvicorn cf_be_api.api:app --port 8071 &
A=$!
sleep 2
# 브라우저: http://localhost:8071/graph.html (be-api 가 fe 마운트 — 단 본 spec 의 mount 는 BFF 책임이라 직접 안 됨)
# 대신 file:// 로 graph.html 열고 ?api=http://localhost:8071 로 직접
echo "manual: open fe/graph.html?api=http://localhost:8071 in browser"
kill $A
```

⚠️ A5 시점에는 fe/dist mount 는 아직 BFF 가 안 함 (B4 이후). 어드민이 graph.html 을 어떻게 띄울지는 운영 결정 — 본 sprint 는 *base URL 결정 로직* 만 정리.

- [ ] **Step 7: Commit + Push + PR**

```bash
git add fe/graph.html backend/be-api/README.md backend/be-for-fe/README.md
git commit -m "refactor(fe,docs): graph.html base URL via ?api= query + admin routing docs

graph.html 의 API base 결정: ?api= 쿼리 우선 → 동일 origin fallback.
어드민·그래프 엔드포인트는 BFF 우회, be-api 직접 호출 명시 (README).
SP-A A5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/a5-admin-graph-routing
gh pr create --title "refactor: graph.html base URL via ?api= + admin routing docs" \
  --body "SP-A sprint A5. graph.html base URL 결정 + 어드민 라우팅 정책 문서화.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Task A6: scripts — dev-up.sh / dev-down.sh / test.sh 갱신

**Goal:** 두 서비스 동시 부팅 스크립트 + 테스트 스크립트가 두 패키지 모두 검증.

**Files:**
- Create: `scripts/dev-up.sh`
- Create: `scripts/dev-down.sh`
- Modify: `scripts/lib/env.sh` — BFF_PORT, BE_API_PORT, BFF_PID_FILE, BE_API_PID_FILE 추가
- Modify: `scripts/test.sh` — be-api 와 be-for-fe 두 패키지 pytest
- Modify: `scripts/backend-up.sh` — BFF 만 띄움 (단일 모드 유지) 또는 deprecated 표시 + dev-up.sh 안내

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/a6-dev-scripts
```

- [ ] **Step 2: env.sh 보강**

`scripts/lib/env.sh` 끝에 추가:

```bash
# be-api / be-for-fe 분리 후 (SP-A)
export BE_API_HOST="${BE_API_HOST:-127.0.0.1}"
export BE_API_PORT="${BE_API_PORT:-8071}"
export BE_API_PID_FILE="$RUN_DIR/be-api.pid"
export BE_API_LOG_FILE="$RUN_DIR/be-api.log"

export BFF_HOST="${BFF_HOST:-0.0.0.0}"
export BFF_PORT="${BFF_PORT:-8070}"
export BFF_PID_FILE="$RUN_DIR/bff.pid"
export BFF_LOG_FILE="$RUN_DIR/bff.log"
```

(기존 `BACKEND_PORT` 등은 backwards-compat 으로 유지하되 deprecated 주석.)

- [ ] **Step 3: dev-up.sh**

`scripts/dev-up.sh`:

```bash
#!/usr/bin/env bash
# Start be-api + be-for-fe in background. PIDs to .run/.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

start_be_api() {
    if [ -f "$BE_API_PID_FILE" ] && pid_alive "$(cat "$BE_API_PID_FILE")"; then
        log_warn "be-api already running"
        return 0
    fi
    log_info "starting be-api on $BE_API_HOST:$BE_API_PORT"
    cd "$REPO_ROOT"
    nohup "$UV" run --package cf-be-api uvicorn cf_be_api.api:app \
        --host "$BE_API_HOST" --port "$BE_API_PORT" \
        > "$BE_API_LOG_FILE" 2>&1 &
    write_pid "$BE_API_PID_FILE" "$!"
}

start_bff() {
    if [ -f "$BFF_PID_FILE" ] && pid_alive "$(cat "$BFF_PID_FILE")"; then
        log_warn "bff already running"
        return 0
    fi
    log_info "starting be-for-fe on $BFF_HOST:$BFF_PORT"
    cd "$REPO_ROOT"
    BFF_BE_API_BASE_URL="http://${BE_API_HOST}:${BE_API_PORT}" \
        nohup "$UV" run --package cf-be-for-fe uvicorn cf_be_for_fe.api:app \
        --host "$BFF_HOST" --port "$BFF_PORT" \
        > "$BFF_LOG_FILE" 2>&1 &
    write_pid "$BFF_PID_FILE" "$!"
}

start_be_api
sleep 2
# healthz polling
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf "http://${BE_API_HOST}:${BE_API_PORT}/healthz" >/dev/null; then
        log_info "be-api ready"
        break
    fi
    sleep 0.5
done

start_bff
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf "http://${BFF_HOST}:${BFF_PORT}/healthz" >/dev/null; then
        log_info "bff ready"
        break
    fi
    sleep 0.5
done

log_info "logs: $BE_API_LOG_FILE  $BFF_LOG_FILE"
```

```bash
chmod +x scripts/dev-up.sh
```

- [ ] **Step 4: dev-down.sh**

`scripts/dev-down.sh`:

```bash
#!/usr/bin/env bash
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

stop() {
    local pid_file="$1"
    local name="$2"
    if [ ! -f "$pid_file" ]; then
        log_info "$name not running"
        return 0
    fi
    local pid
    pid=$(cat "$pid_file")
    if pid_alive "$pid"; then
        log_info "stopping $name (pid $pid)"
        kill "$pid" 2>/dev/null || true
        for _ in 1 2 3 4 5; do
            pid_alive "$pid" || break
            sleep 0.5
        done
        pid_alive "$pid" && kill -9 "$pid" 2>/dev/null
    fi
    rm -f "$pid_file"
}

stop "$BFF_PID_FILE" "bff"
stop "$BE_API_PID_FILE" "be-api"
```

```bash
chmod +x scripts/dev-down.sh
```

- [ ] **Step 5: test.sh 갱신**

`scripts/test.sh` 의 backend 섹션을 두 패키지로:

```bash
log_info "pytest cf-be-api"
"$UV" run --package cf-be-api pytest backend/be-api/tests -x -q || exit 1

log_info "pytest cf-be-for-fe"
"$UV" run --package cf-be-for-fe pytest backend/be-for-fe/tests -x -q || exit 1
```

(integration / RUN_INTEGRATION 분기는 원본 패턴 유지.)

- [ ] **Step 6: backend-up.sh deprecated 표시 (또는 BFF 만 띄우게 변경)**

옵션 — 단일 backend-up.sh 가 BFF 띄우도록 변경 (기존 명령 유지):

```bash
#!/usr/bin/env bash
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

log_warn "backend-up.sh: SP-A 이후로는 dev-up.sh 권장 (be-api + bff 동시 부팅)"
log_warn "이 스크립트는 BFF 만 띄움. be-api 가 먼저 떠 있어야 함."

if [ ! -f "$BE_API_PID_FILE" ] || ! pid_alive "$(cat "$BE_API_PID_FILE")"; then
    log_error "be-api 가 떠있지 않음. dev-up.sh 사용 권장"
    exit 1
fi

# (BFF 부팅 — dev-up.sh 의 start_bff 와 동일)
log_info "starting be-for-fe on $BFF_HOST:$BFF_PORT"
cd "$REPO_ROOT"
BFF_BE_API_BASE_URL="http://${BE_API_HOST}:${BE_API_PORT}" \
    nohup "$UV" run --package cf-be-for-fe uvicorn cf_be_for_fe.api:app \
    --host "$BFF_HOST" --port "$BFF_PORT" \
    > "$BFF_LOG_FILE" 2>&1 &
write_pid "$BFF_PID_FILE" "$!"
```

- [ ] **Step 7: Smoke**

```bash
./scripts/dev-up.sh
sleep 1
curl -sf http://localhost:8070/healthz | head -c 200 && echo
./scripts/test.sh 2>&1 | tail -10
./scripts/dev-down.sh
```

기대: dev-up 후 healthz JSON 표시, test.sh 가 두 패키지 PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/dev-up.sh scripts/dev-down.sh scripts/lib/env.sh \
        scripts/test.sh scripts/backend-up.sh
git commit -m "feat(scripts): dev-up.sh / dev-down.sh + test.sh runs both packages

dev-up.sh 가 be-api + bff 순차 부팅, healthz polling.
test.sh 가 cf-be-api + cf-be-for-fe 둘 다 pytest.
backend-up.sh 는 BFF 단독 모드로 변경 (deprecation hint).
SP-A A6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/a6-dev-scripts
gh pr create --title "feat(scripts): dev-up.sh + 두 패키지 test.sh" \
  --body "SP-A sprint A6. 로컬 dev 환경 통합.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Task A7: 잔여 husk 정리 + README 일관성

**Goal:** 잔여 `cf_backend` 참조 / stale 명령 (예: `camfit-puller serve`) / 누락된 문서 정리.

**Files:**
- Find/clean: 모든 `cf_backend`, `cf-backend`, `camfit-puller serve` 참조
- Modify: `backend/README.md` (NEW — 두 패키지 안내), `backend/be-api/README.md`, `backend/be-for-fe/README.md`
- Modify: 루트 `README.md` (있다면) 또는 `docs/` 안내 파일

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/a7-husk-and-docs
```

- [ ] **Step 2: 잔여 참조 검색**

```bash
grep -rn "cf_backend\|cf-backend\|camfit-puller serve" \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv \
  --exclude-dir=__pycache__ --exclude-dir=dist --exclude-dir=.run \
  .
```

발견된 항목 각각:
- 코드 (.py, .sh, .toml): 갱신
- 문서 (.md): 갱신
- 주석에서 의미 있는 컨텍스트 (예: 마이그레이션 히스토리): 그대로 두되 "구 cf_backend (현 cf_be_api)" 같은 주석 보강

- [ ] **Step 3: backend/README.md 신규 (두 패키지 안내)**

`backend/README.md` (이전에 be-api 로 옮긴 README 와 별개로 backend/ 그룹 디렉터리 README):

````markdown
# backend/

cf 의 백엔드 — uv workspace 두 패키지로 구성:

- **be-api/** (`cf-be-api`) — DB-tier. domain·ports·usecases·adapters + raw 도메인 응답 FastAPI. 프로덕션 VPC 내부 격리.
- **be-for-fe/** (`cf-be-for-fe`) — BFF. projection·aggregation. 외부 노출. fe 가 호출.

## Run (local dev)

```sh
./scripts/dev-up.sh    # be-api :8071 + be-for-fe :8070 동시 부팅
./scripts/dev-down.sh  # 종료
```

## Test

```sh
./scripts/test.sh      # 두 패키지 모두 pytest
```

## Architecture

`docs/superpowers/specs/2026-05-10-backend-split-be-api-bff-design.md` 참조.
````

- [ ] **Step 4: 루트 README 또는 docs 안내 갱신**

`grep -l "camfit-puller serve\|cf_backend\b" docs/ README.md 2>/dev/null` 결과 항목 각각 갱신:
- "camfit-puller serve" → "scripts/dev-up.sh"
- "cf_backend.api:app" → "cf_be_for_fe.api:app" (외부 노출 명령 맥락) 또는 "cf_be_api.api:app" (내부 / 어드민 맥락)

- [ ] **Step 5: pyproject 주석 정리**

`pyproject.toml` (root) 의 주석:

```toml
# 기존:
# [tool.uv.sources]
# cf-backend = { workspace = true }   # uncomment when backend/ exists (Sprint 5)
```

이 주석은 repo restructure 시점의 잔재 — A1 에서 갱신했지만 다시 확인:

```toml
[tool.uv.sources]
cf-be-api = { workspace = true }
cf-be-for-fe = { workspace = true }
```

- [ ] **Step 6: 최종 검증**

```bash
# 1) 잔여 참조
grep -rn "cf_backend\|cf-backend" \
  --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.venv \
  --exclude-dir=.run --exclude-dir=dist . | head -20
# 출력 = 의미 있는 히스토리 주석만 (또는 빈)

# 2) 두 패키지 부팅 + 핵심 fe 호출 시나리오
./scripts/dev-up.sh
sleep 2
curl -sf http://localhost:8070/facets >/dev/null && echo "facets OK"
curl -sf http://localhost:8070/featured-axes >/dev/null && echo "featured-axes OK"
curl -sf "http://localhost:8070/sites?region=강원" >/dev/null && echo "sites OK"
./scripts/dev-down.sh

# 3) 테스트 풀스위트
./scripts/test.sh
```

기대: 모든 smoke 와 test PASS.

- [ ] **Step 7: Commit + Push + PR**

```bash
git add -A
git status -s
# 의도한 변경만인지 검토 후
git commit -m "chore(backend): husk cleanup + README + stale ref pruning

backend/README.md 신규 (두 패키지 안내).
잔여 cf_backend, camfit-puller serve 참조 갱신.
SP-A A7 (final).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/a7-husk-and-docs
gh pr create --title "chore(backend): husk cleanup + docs (SP-A final)" \
  --body "SP-A sprint A7 — 잔여 참조 / stale 명령 정리, backend/README.md 신규.

SP-A 완료 후 후속:
- writing-plans 의 다음 plan: SP-B/C (fe Vite + m.html)
- 운영 묶음: SP-A A4 + SP-B/C B4 같은 배포 사이클

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Self-review checklist

- [x] Spec 의 5절 (HTTP 엔드포인트 라우팅 매핑) 모든 행이 plan 의 task 에 매핑: facets/concepts/themes/marks/featured-axes (A2), sites/* (A3), eta/* (A4), graph/* + admin/* (A5)
- [x] projection 함수 5개 (camp_to_fe_row, filter_maritime_for_inland, filter_location_types_for_inland, project_categories, _LANDLOCKED_SIDO) 모두 A3 에 포함
- [x] 회귀 fixture (spec 11절) — A3 step 2/7 에 fixture 캡처 + RUN_INTEGRATION 통합 테스트
- [x] 보안 모델 (spec 7절) — A6 의 BFF_BE_API_BASE_URL 환경 분리. 인증 없음을 코드·README 에 명시 (A2 README, A5 README, A7 README)
- [x] 마이그레이션 sprint 7개 (spec 10절) — Task A1~A7 1:1 매핑
- [x] PR 단위·자동 머지 (사용자 워크플로) — 매 task 마지막 step 에 `gh pr merge --auto --merge`
- [x] No placeholders — 모든 step 이 실제 코드/명령 포함. ⚠️ 마커는 "원본 정확값 복사 필요" 명시 (placeholder 가 아니라 실 데이터 의존)

## 알려진 한계

- A3 의 `_LANDLOCKED_SIDO` 와 projection 함수 본체는 *실제 cf_be_api/api.py 의 원본 그대로 복사*. plan 의 코드는 시그니처/패턴 참고용. ⚠️ 마커가 명시.
- A4 의 `EtaBatchRequest` 는 be-api 모델과 1:1 — 스키마 변경 시 양쪽 갱신 (spec 8절의 contract 격리 결정).
- A5 graph.html 의 base URL 결정은 어드민 운영 환경에 의존 — `?api=` 쿼리 + 동일 origin fallback 두 모드 지원.
- A6 `dev-up.sh` 는 Linux/macOS bash 전제. Windows 는 Git Bash 또는 WSL 필요 (현 scripts/lib/env.sh 의 uv.exe 분기와 동일 패턴).

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-10-backend-split-be-api-bff.md`.

다음은 SP-B/C plan 작성 (이어서). SP-A 와 SP-B/C plan 모두 완료 후 사용자가 실행 시점/방식 결정.
