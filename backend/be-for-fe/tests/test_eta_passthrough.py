"""A4 — /eta* BFF→be-api 통과 검증.

GET /eta, POST /eta/batch, DELETE /eta/cache 모두 본문 가공 없이 전달.
"""
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
def test_eta_one_passthrough(client):
    sample = {"origin": "서울 강남구", "dest": "강원 춘천", "minutes": 95, "source": "etago"}
    route = respx.get("http://localhost:8071/eta").mock(return_value=Response(200, json=sample))

    r = client.get("/eta", params={"origin": "서울 강남구", "dest": "강원 춘천", "timeout_s": 8.0})
    assert r.status_code == 200
    assert r.json() == sample
    assert route.called
    qs = dict(route.calls.last.request.url.params)
    assert qs == {"origin": "서울 강남구", "dest": "강원 춘천", "timeout_s": "8.0"}


@respx.mock
def test_eta_batch_post_forward(client):
    body = {
        "origin": "서울 강남구",
        "ids": ["camp-1", "camp-2"],
        "max_minutes": 180,
        "concurrency": 4,
        "timeout_s": 12.0,
    }
    sample = {
        "results": {
            "camp-1": {"minutes": 95, "source": "etago"},
            "camp-2": {"minutes": 132, "source": "etago"},
        },
        "skipped_over_max": 0,
    }
    route = respx.post("http://localhost:8071/eta/batch").mock(
        return_value=Response(200, json=sample)
    )
    r = client.post("/eta/batch", json=body)
    assert r.status_code == 200
    assert r.json() == sample
    assert route.called
    # be-api 가 받는 body 가 정확히 우리 Pydantic 모델 dump 형태
    import json as _json
    forwarded = _json.loads(route.calls.last.request.content)
    assert forwarded == body


@respx.mock
def test_eta_cache_delete(client):
    route = respx.delete("http://localhost:8071/eta/cache").mock(
        return_value=Response(200, json={"cleared": 42})
    )
    r = client.delete("/eta/cache")
    assert r.status_code == 200
    assert r.json() == {"cleared": 42}
    assert route.called


@respx.mock
def test_eta_cache_5xx_becomes_503(client):
    """delete() 가 BeApiError 로 감싸지는지 — A2 review note."""
    respx.delete("http://localhost:8071/eta/cache").mock(return_value=Response(500))
    r = client.delete("/eta/cache")
    assert r.status_code == 503
