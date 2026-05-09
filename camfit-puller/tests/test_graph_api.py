"""Unit tests for /graph/* endpoints — mock FalkorDB via monkeypatch.

Each fake `result_set` is a list of rows in FalkorDB driver shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from camfit_puller import api as api_mod


@dataclass
class FakeResult:
    result_set: list[list[Any]]


class FakeGraph:
    """Pretends to be a FalkorDB graph. `responses` maps a Cypher *prefix* to a
    callable returning rows; falls back to empty result if no match."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def query(self, cypher: str, params: dict | None = None) -> FakeResult:
        self.calls.append((cypher, params or {}))
        for prefix, handler in self.responses.items():
            if prefix in cypher:
                rows = handler(params or {})
                return FakeResult(rows)
        return FakeResult([])


@pytest.fixture
def client():
    return TestClient(api_mod.app)


def _patch_falkor(monkeypatch, fake: FakeGraph):
    monkeypatch.setattr(api_mod, "_falkor", lambda: fake)


# ─────────────────────────────────────────────────────────────────────────
# /graph/schema
# ─────────────────────────────────────────────────────────────────────────


def test_schema_lists_labels_and_edges_with_counts(monkeypatch, client):
    fake = FakeGraph({
        "CALL db.labels()": lambda p: [["Camp"], ["Region"]],
        "CALL db.relationshipTypes()": lambda p: [["LOCATED_IN"]],
        "MATCH (n:`Camp`) RETURN count(n)": lambda p: [[3]],
        "MATCH (n:`Region`) RETURN count(n)": lambda p: [[2]],
        "MATCH (n:`Camp`) RETURN keys(n)": lambda p: [[["id", "name", "lat"]], [["id", "name"]]],
        "MATCH (n:`Region`) RETURN keys(n)": lambda p: [[["sido", "sigungu"]]],
        "MATCH ()-[r:`LOCATED_IN`]->() RETURN count(r)": lambda p: [[3]],
    })
    _patch_falkor(monkeypatch, fake)

    r = client.get("/graph/schema")
    assert r.status_code == 200
    data = r.json()
    names = {l["name"] for l in data["labels"]}
    assert names == {"Camp", "Region"}
    by_name = {l["name"]: l for l in data["labels"]}
    assert by_name["Camp"]["count"] == 3
    assert "id" in by_name["Camp"]["keys"]
    assert by_name["Region"]["keys"] == ["sido", "sigungu"]
    assert data["edges"] == [{"name": "LOCATED_IN", "count": 3}]


def test_schema_graceful_when_falkor_down(monkeypatch, client):
    def boom():
        raise ConnectionError("falkor unreachable")

    monkeypatch.setattr(api_mod, "_falkor", boom)

    r = client.get("/graph/schema")
    assert r.status_code == 200
    assert r.json() == {"labels": [], "edges": []}
    assert "falkor" in r.headers.get("x-warning", "").lower()


# ─────────────────────────────────────────────────────────────────────────
# /graph/sample
# ─────────────────────────────────────────────────────────────────────────


def test_sample_returns_cytoscape_elements_with_synthetic_ids(monkeypatch, client):
    # row shape per /graph/sample (undirected): l_n, p_n, r_t, r_dir, l_m, p_m
    rows = [
        ["Camp", {"id": "abc", "name": "캠프A"}, "LOCATED_IN", "out",
         "Region", {"sido": "강원", "sigungu": "평창군"}],
        ["Camp", {"id": "def", "name": "캠프B"}, None, None, None, None],
    ]
    fake = FakeGraph({"MATCH (n)": lambda p: rows})
    _patch_falkor(monkeypatch, fake)

    r = client.get("/graph/sample?limit=10")
    data = r.json()
    node_ids = {n["data"]["id"] for n in data["nodes"]}
    assert "Camp:abc" in node_ids
    assert "Camp:def" in node_ids
    assert "Region:강원|평창군" in node_ids

    edges = data["edges"]
    assert len(edges) == 1
    e = edges[0]["data"]
    assert e["source"] == "Camp:abc"
    assert e["target"] == "Region:강원|평창군"
    assert e["label"] == "LOCATED_IN"


def test_sample_handles_incoming_edges_when_seeded_on_target_label(monkeypatch, client):
    # When user seeds with labels=Region, the edges go INTO Region — the
    # backend must still return them as Camp -> Region (correct direction).
    rows = [
        ["Region", {"sido": "강원", "sigungu": "평창군"}, "LOCATED_IN", "in",
         "Camp", {"id": "abc", "name": "캠프A"}],
    ]
    fake = FakeGraph({"MATCH (n)": lambda p: rows})
    _patch_falkor(monkeypatch, fake)

    data = client.get("/graph/sample?labels=Region&limit=10").json()
    edges = data["edges"]
    assert len(edges) == 1
    e = edges[0]["data"]
    assert e["source"] == "Camp:abc"
    assert e["target"] == "Region:강원|평창군"


def test_sample_dedupes_edge_when_both_endpoints_in_limit(monkeypatch, client):
    # Same edge appears in both rows (Camp side + Region side) — must dedup.
    rows = [
        ["Camp", {"id": "abc", "name": "A"}, "LOCATED_IN", "out",
         "Region", {"sido": "강원", "sigungu": "평창"}],
        ["Region", {"sido": "강원", "sigungu": "평창"}, "LOCATED_IN", "in",
         "Camp", {"id": "abc", "name": "A"}],
    ]
    fake = FakeGraph({"MATCH (n)": lambda p: rows})
    _patch_falkor(monkeypatch, fake)

    data = client.get("/graph/sample?limit=10").json()
    assert len(data["edges"]) == 1


def test_sample_respects_label_filter(monkeypatch, client):
    captured = {}

    def handler(p):
        captured["params"] = p
        return []

    fake = FakeGraph({"WHERE labels(n)[0] IN $labels": handler})
    _patch_falkor(monkeypatch, fake)

    client.get("/graph/sample?labels=Camp,Region&limit=50")
    assert captured["params"]["labels"] == ["Camp", "Region"]
    assert captured["params"]["limit"] == 50


# ─────────────────────────────────────────────────────────────────────────
# /graph/expand
# ─────────────────────────────────────────────────────────────────────────


def test_expand_parses_synthetic_id_and_returns_neighbors(monkeypatch, client):
    captured = {}

    def handler(p):
        captured["params"] = p
        return [
            ["Camp", {"id": "abc", "name": "캠프A"}, "HAS_CATEGORY", "out", "Category", {"name": "계곡"}],
            ["Camp", {"id": "abc", "name": "캠프A"}, "LOCATED_IN", "out", "Region", {"sido": "강원", "sigungu": "평창군"}],
        ]

    fake = FakeGraph({"MATCH (n:`Camp`) WHERE": handler})
    _patch_falkor(monkeypatch, fake)

    r = client.get("/graph/expand?id=Camp:abc&direction=out&limit=20")
    assert r.status_code == 200
    assert captured["params"]["k_id"] == "abc"
    data = r.json()
    node_ids = {n["data"]["id"] for n in data["nodes"]}
    assert {"Camp:abc", "Category:계곡", "Region:강원|평창군"}.issubset(node_ids)
    edge_targets = {e["data"]["target"] for e in data["edges"]}
    assert "Category:계곡" in edge_targets


def test_expand_handles_composite_natural_key(monkeypatch, client):
    captured = {}

    def handler(p):
        captured["params"] = p
        return []

    fake = FakeGraph({"MATCH (n:`Region`) WHERE": handler})
    _patch_falkor(monkeypatch, fake)

    client.get("/graph/expand?id=Region:강원|평창군")
    p = captured["params"]
    assert p.get("k_sido") == "강원"
    assert p.get("k_sigungu") == "평창군"


def test_expand_invalid_id_returns_empty(monkeypatch, client):
    monkeypatch.setattr(api_mod, "_falkor", lambda: FakeGraph({}))
    r = client.get("/graph/expand?id=garbage")
    assert r.status_code == 200
    assert r.json() == {"nodes": [], "edges": []}


# ─────────────────────────────────────────────────────────────────────────
# /graph/search
# ─────────────────────────────────────────────────────────────────────────


def test_search_with_label_uses_primary_text_key(monkeypatch, client):
    captured = {}

    def handler(p):
        captured["params"] = p
        return [["Camp", {"id": "abc", "name": "노을 캠프"}]]

    fake = FakeGraph({"MATCH (n:`Camp`)": handler})
    _patch_falkor(monkeypatch, fake)

    r = client.get("/graph/search?q=노을&label=Camp&limit=5")
    assert r.status_code == 200
    assert captured["params"]["q"] == "노을"
    nodes = r.json()["nodes"]
    assert nodes[0]["data"]["id"] == "Camp:abc"
    assert nodes[0]["data"]["label"] == "Camp"


def test_search_without_label_iterates_all_labels(monkeypatch, client):
    fake = FakeGraph({
        "CALL db.labels()": lambda p: [["Camp"], ["Category"]],
        "MATCH (n:`Camp`)": lambda p: [["Camp", {"id": "abc", "name": "노을 캠프"}]],
        "MATCH (n:`Category`)": lambda p: [["Category", {"name": "노을맛집"}]],
    })
    _patch_falkor(monkeypatch, fake)

    r = client.get("/graph/search?q=노을&limit=10")
    data = r.json()
    ids = {n["data"]["id"] for n in data["nodes"]}
    assert ids == {"Camp:abc", "Category:노을맛집"}
