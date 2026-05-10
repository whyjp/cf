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
