"""BFF FastAPI surface — fe 가 호출. be-api 를 httpx 로 통과·변환.

- A2: 얇은 통과 (facets/concepts/themes/marks/featured-axes)
- A3: /sites* 라우팅 + projection (be-api 가 raw Camp dict 반환 → BFF 가 fe-row 로 가공)
- A4: /eta* 통과 (예정)
"""
from __future__ import annotations
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
