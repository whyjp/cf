"""BFF FastAPI surface — fe 가 호출. be-api 를 httpx 로 통과·변환.

- A2: 얇은 통과 (facets/concepts/themes/marks/featured-axes)
- A3: /sites* 라우팅 + projection (be-api 가 raw Camp dict 반환 → BFF 가 fe-row 로 가공)
- A4: /eta* 통과 (단일/배치/캐시 무효화)
- C5: UA-based "/" 라우팅 — 모바일 UA + !prefer_desktop → /m.html 302
"""
from __future__ import annotations
import re
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .settings import Settings
from .client import BeApiClient, BeApiError
from .projection import project_camps, camp_to_fe_row, project_site_detail

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


# ───────────────────────── /sites* — A3 projection ─────────────────────
#
# be-api 는 raw Camp 도메인 dict (Camp.model_dump()) 반환. 여기서 fe-friendly
# flat row 로 가공. 사전 캡처된 fixtures/regression/before_a3_*.json 와 byte
# 동일 응답이 나와야 함 (test_sites_projection.py).

@app.get("/sites")
def sites(
    region: Optional[str] = None,
    sigungu: Optional[str] = None,
    concept: list[str] = Query(default_factory=list, description="AND of concepts (repeat ?concept=)"),
    concepts_any: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    bbox: Optional[str] = None,
    limit: int = 2000,
) -> list[dict]:
    raw = _passthrough_get(
        "/sites",
        region=region, sigungu=sigungu,
        # 빈 list 면 forward 안 함 (be-api 의 None 디폴트와 동등)
        concept=(concept or None),
        concepts_any=concepts_any,
        min_score=min_score, max_score=max_score,
        bbox=bbox, limit=limit,
    )
    if not isinstance(raw, list):
        raise HTTPException(status_code=502, detail="be-api /sites returned non-list")
    return project_camps(raw)


@app.get("/sites/search")
def site_search(q: str = Query(..., min_length=1), k: int = 20) -> list[dict]:
    raw = _passthrough_get("/sites/search", q=q, k=k)
    if not isinstance(raw, list):
        raise HTTPException(status_code=502, detail="be-api /sites/search returned non-list")
    return project_camps(raw)


@app.get("/sites/{site_id}/similar")
def site_similar(site_id: str, k: int = 10) -> list[dict]:
    raw = _passthrough_get(f"/sites/{site_id}/similar", k=k)
    if not isinstance(raw, list):
        raise HTTPException(status_code=502, detail="be-api /sites/{id}/similar returned non-list")
    return project_camps(raw)


@app.get("/sites/{site_id}")
def site_detail(site_id: str) -> dict:
    raw = _passthrough_get(f"/sites/{site_id}")
    return project_site_detail(raw)


# ───────────────────────── /eta* — A4 통과 ───────────────────────────────
#
# be-api 의 /eta* 시그니처를 그대로 미러. origin/dest 는 *문자열 주소* (etago
# 가 직접 받아쓰는 형식). 본문 가공 없음 — fe 는 be-api 응답 형태를 동일하게
# 받음. EtaBatchRequest 는 be-api 의 동일 클래스와 필드/제약 일치.

class EtaBatchRequest(BaseModel):
    origin: str = Field(..., min_length=1)
    ids: list[str] = Field(..., min_length=1, max_length=10000)
    max_minutes: Optional[int] = Field(None, ge=1, le=1440)
    concurrency: int = Field(4, ge=1, le=12)
    timeout_s: float = Field(12.0, ge=2.0, le=60.0)


@app.get("/eta")
def eta_one(
    origin: str = Query(..., min_length=1),
    dest: str = Query(..., min_length=1),
    timeout_s: float = Query(12.0, ge=2.0, le=60.0),
) -> dict:
    return _passthrough_get("/eta", origin=origin, dest=dest, timeout_s=timeout_s)


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


# ───────────────────────── C5: "/" UA-based routing ───────────────────────
#
# Mobile UA + no prefer_desktop cookie → 302 /m.html
# Desktop UA + prefer_mobile cookie    → 302 /m.html
# Else → FileResponse fe/dist/index.html
#
# ⚠️ Order: this `@app.get("/")` MUST come BEFORE `app.mount("/", StaticFiles)`
# below. The StaticFiles catch-all otherwise wins for "/" and "Mobi" UAs would
# always hit the desktop bundle.

MOBILE_UA_RE = re.compile(r"Mobi|Android|iPhone|iPad|iPod", re.I)


@app.get("/", include_in_schema=False)
def root_redirect(request: Request):
    """UA + cookie 기반 진입 라우팅 (C5)."""
    ua = request.headers.get("user-agent", "")
    is_mobile_ua = bool(MOBILE_UA_RE.search(ua))
    prefer_desktop = request.cookies.get("prefer_desktop") == "1"
    prefer_mobile = request.cookies.get("prefer_mobile") == "1"

    if is_mobile_ua and not prefer_desktop:
        return RedirectResponse("/m.html", status_code=302)
    if not is_mobile_ua and prefer_mobile:
        return RedirectResponse("/m.html", status_code=302)

    index = _settings.fe_dir / "index.html"
    if not index.is_file():
        # fe/dist 가 아직 없는 환경 — 503 으로 빌드 필요 신호
        raise HTTPException(status_code=503, detail="fe/dist/index.html not built yet")
    return FileResponse(index)


# ───────────────────────── FE static mount (SP-B B4) ─────────────────────
#
# BFF serves fe/dist/ at "/" — Vite build output. Must be defined LAST so
# concrete /sites, /facets, /healthz routes above take precedence over the
# catch-all StaticFiles handler.
#
# `is_dir()` guard: in CI cold env or before `npm run build`, fe/dist may not
# exist. Skip mount in that case (BFF still serves API routes; "/" 404s).
# Run `cd fe && npm run build` to produce the static bundle.

_fe_path = _settings.fe_dir
if _fe_path.is_dir():
    app.mount("/", StaticFiles(directory=str(_fe_path), html=True), name="fe")
