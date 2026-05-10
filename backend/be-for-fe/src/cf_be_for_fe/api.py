"""BFF FastAPI surface — fe 가 호출. be-api 를 httpx 로 통과·변환.

A2 시점: 얇은 통과 only. projection (sites/*) 은 A3, /eta* 는 A4.
"""
from __future__ import annotations
from typing import Optional, Any

from fastapi import FastAPI, HTTPException
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
