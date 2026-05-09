"""FastAPI read API consumed by fe/index.html.

Endpoints:
    GET /sites?region=&category=&facility=&bbox=lon1,lat1,lon2,lat2
    GET /sites/{id}
    GET /facets             (regions/categories/facilities counts)
    GET /healthz

Sources:
    - Primary list: FalkorDB (Cypher) for filterable graph queries.
    - Detail: FalkorDB KG only (RocksDB removed in T36; full PG migration in T37).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from falkordb import FalkorDB
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .etago_adapter import EtagoClient, EtagoUnavailable


FALKOR_HOST = os.environ.get("FALKOR_HOST", "localhost")
FALKOR_PORT = int(os.environ.get("FALKOR_PORT", "6379"))
FALKOR_GRAPH = os.environ.get("FALKOR_GRAPH", "camfit")
FE_DIR = os.environ.get("CAMFIT_FE_DIR", str(Path(__file__).resolve().parents[3] / "fe"))


def _falkor():
    return FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(FALKOR_GRAPH)


app = FastAPI(title="camfit-puller API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# Lazy etago client — instantiated on first use so the API can boot even if
# the etago binary is absent. Endpoints surface a clean 503 in that case.
_etago: Optional[EtagoClient] = None


def _get_etago() -> EtagoClient:
    global _etago
    if _etago is None:
        try:
            _etago = EtagoClient()
        except EtagoUnavailable as e:
            raise HTTPException(503, str(e))
    return _etago


@app.get("/healthz")
def healthz() -> dict:
    status = {"falkor": "down", "etago": "down"}
    try:
        _falkor().query("RETURN 1")
        status["falkor"] = "up"
    except Exception:
        pass
    try:
        EtagoClient()  # will raise if binary not found
        status["etago"] = "up"
    except EtagoUnavailable:
        pass
    return status


@app.get("/facets")
def facets() -> dict:
    out = {"regions": [], "categories": [], "facilities": []}
    try:
        g = _falkor()
        rs = g.query(
            "MATCH (r:Region)<-[:LOCATED_IN]-(c:Camp) "
            "RETURN r.sido AS sido, r.sigungu AS sigungu, count(c) AS n "
            "ORDER BY n DESC"
        ).result_set
        out["regions"] = [{"sido": r[0], "sigungu": r[1], "count": int(r[2])} for r in rs]
        rs = g.query(
            "MATCH (cat:Category)<-[:HAS_CATEGORY]-(c:Camp) "
            "RETURN cat.name AS name, count(c) AS n ORDER BY n DESC"
        ).result_set
        out["categories"] = [{"name": r[0], "count": int(r[1])} for r in rs]
        rs = g.query(
            "MATCH (f:Facility)<-[:HAS_FACILITY]-(c:Camp) "
            "RETURN f.name AS name, count(c) AS n ORDER BY n DESC"
        ).result_set
        out["facilities"] = [{"name": r[0], "count": int(r[1])} for r in rs]
    except Exception as e:
        return JSONResponse(out, status_code=200, headers={"X-Warning": f"falkor: {type(e).__name__}"})
    return out


def _parse_bbox(bbox: Optional[str]) -> Optional[tuple[float, float, float, float]]:
    if not bbox:
        return None
    parts = bbox.split(",")
    if len(parts) != 4:
        return None
    try:
        a, b, c, d = (float(x) for x in parts)
        return a, b, c, d
    except ValueError:
        return None


@app.get("/sites")
def sites(
    region: Optional[str] = None,
    category: Optional[str] = None,
    facility: Optional[str] = None,
    has_valley: Optional[bool] = None,
    has_kids: Optional[bool] = None,
    has_trampoline: Optional[bool] = None,
    bbox: Optional[str] = Query(None, description="lon1,lat1,lon2,lat2"),
    limit: int = 2000,
) -> list[dict]:
    where = ["c.id IS NOT NULL"]
    params: dict = {"limit": limit}
    if region:
        where.append("(r.sido = $region OR r.sigungu = $region)")
        params["region"] = region
    if has_valley is not None:
        where.append("c.has_valley = $hv")
        params["hv"] = bool(has_valley)
    if has_kids is not None:
        where.append("c.has_kids = $hk")
        params["hk"] = bool(has_kids)
    if has_trampoline is not None:
        where.append("c.has_trampoline = $ht")
        params["ht"] = bool(has_trampoline)
    bb = _parse_bbox(bbox)
    if bb:
        lon1, lat1, lon2, lat2 = bb
        where.append("c.lon >= $lon1 AND c.lon <= $lon2 AND c.lat >= $lat1 AND c.lat <= $lat2")
        params.update({"lon1": min(lon1, lon2), "lon2": max(lon1, lon2),
                       "lat1": min(lat1, lat2), "lat2": max(lat1, lat2)})

    where_clause = " AND ".join(where)
    cypher = (
        "MATCH (c:Camp)-[:LOCATED_IN]->(r:Region) "
        f"WHERE {where_clause} "
    )
    if category:
        cypher += "MATCH (c)-[:HAS_CATEGORY]->(:Category {name: $category}) "
        params["category"] = category
    if facility:
        cypher += "MATCH (c)-[:HAS_FACILITY]->(:Facility {name: $facility}) "
        params["facility"] = facility
    # Two sequential WITH+collect to avoid cartesian product across categories × facilities.
    cypher += (
        "OPTIONAL MATCH (c)-[:HAS_CATEGORY]->(cat:Category) "
        "WITH c, r, collect(DISTINCT cat.name) AS cats "
        "OPTIONAL MATCH (c)-[:HAS_FACILITY]->(f:Facility) "
        "WITH c, r, cats, collect(DISTINCT f.name) AS facs "
        "RETURN c.id, c.name, c.lat, c.lon, r.sido, r.sigungu, "
        "       c.has_valley, c.has_kids, c.has_trampoline, c.url, cats, facs "
        "LIMIT $limit"
    )

    try:
        rs = _falkor().query(cypher, params=params).result_set
    except Exception:
        return []
    out: list[dict] = []
    for row in rs:
        out.append({
            "id": row[0],
            "name": row[1],
            "lat": row[2],
            "lon": row[3],
            "sido": row[4],
            "sigungu": row[5],
            "has_valley": bool(row[6]),
            "has_kids": bool(row[7]),
            "has_trampoline": bool(row[8]),
            "url": row[9],
            "categories": [c for c in (row[10] or []) if c],
            "facilities": [f for f in (row[11] or []) if f],
        })
    return out


@app.get("/sites/{site_id}")
def site_detail(site_id: str) -> dict:
    """Camp detail from FalkorDB KG.

    Response shape:
        { ...summary fields..., detail: null, reviews: null }

    # T37: TODO migrate to GetSiteDetail use-case (PG-backed detail + reviews).
    # RocksDB was removed in T36. detail/reviews fields are null until T37 wires PG.
    """
    summary: dict | None = None
    detail: dict | None = None
    reviews: dict | None = None

    # T37: TODO fetch detail and reviews from PG (GetSiteDetail use-case).

    # KG lookup for summary.
    try:
        rs = _falkor().query(
            "MATCH (c:Camp {id: $id})-[:LOCATED_IN]->(r:Region) "
            "OPTIONAL MATCH (c)-[:HAS_CATEGORY]->(cat:Category) "
            "OPTIONAL MATCH (c)-[:HAS_FACILITY]->(f:Facility) "
            "RETURN c.id, c.name, c.lat, c.lon, c.url, r.sido, r.sigungu, "
            "       collect(DISTINCT cat.name), collect(DISTINCT f.name)",
            params={"id": site_id},
        ).result_set
        if not rs:
            raise HTTPException(404, f"camp {site_id} not found")
        row = rs[0]
        summary = {
            "id": row[0], "name": row[1], "lat": row[2], "lon": row[3], "url": row[4],
            "region_sido": row[5], "region_sigungu": row[6],
            "categories": [c for c in row[7] if c],
            "facilities": [f for f in row[8] if f],
            "_source": "kg-only",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, f"falkor unavailable: {e}")

    enriched = dict(summary)
    if detail:
        # Surface the most useful detail fields directly + keep raw under "_detail".
        enriched.setdefault("description", detail.get("description"))
        enriched.setdefault("address1", detail.get("address1"))
        enriched.setdefault("address2", detail.get("address2"))
        enriched.setdefault("brief", detail.get("brief"))
        enriched.setdefault("locationBrief", detail.get("locationBrief"))
        enriched.setdefault("contact", detail.get("contact"))
        enriched.setdefault("hashtags", detail.get("hashtags") or [])
        enriched.setdefault("locationTypes", detail.get("locationTypes") or [])
        # Merge facility lists for FE display
        f_inv = list(detail.get("facilities") or [])
        f_add = list(detail.get("additionalFacilities") or [])
        merged_facs = sorted(set((enriched.get("facilities") or []) + f_inv + f_add))
        enriched["facilities"] = merged_facs
        # Pricing
        enriched.setdefault("priceStartFrom", detail.get("priceStartFrom"))
        enriched.setdefault("priceEndTo", detail.get("priceEndTo"))
        # Photo medias — slim to URLs
        medias = detail.get("medias") or []
        slim = []
        for m in medias[:8]:
            slim.append({
                "url": m.get("url"),
                "thumb": ((m.get("formats") or {}).get("small") or {}).get("url") or m.get("url"),
            })
        enriched["photos"] = slim
        enriched["numOfReviews"] = (
            (reviews or {}).get("pagination", {}).get("total")
            or detail.get("numOfReviews")
            or 0
        )
        enriched["bookmarkCount"] = detail.get("bookmarkCount")

    if reviews:
        items = []
        # Sort by totalScore (recommend), top 3
        rsorted = sorted(reviews.get("reviews") or [], key=lambda r: -(r.get("totalScore") or 0))[:3]
        for rv in rsorted:
            items.append({
                "user": (rv.get("user") or {}).get("nickname") or "익명",
                "season": rv.get("season"),
                "userType": rv.get("userType"),
                "score": rv.get("totalScore"),
                "text": rv.get("text") or "",
                "numOfDays": rv.get("numOfDays"),
            })
        enriched["reviews_top"] = items
        enriched["reviews_total"] = (reviews.get("pagination") or {}).get("total")

    return enriched


# ─────────────────────────────────────────────────────────────────────────
# ETA (drive-time filter) — wraps sibling `etago` Go binary
# ─────────────────────────────────────────────────────────────────────────


def _place_for_camp(payload: dict) -> str:
    """Pick the most etago-friendly place string from a camp record.

    etago wraps Naver/Kakao web map search — these geocode best with
    *administrative* place names (시도+시군구), not free-form camp names or
    addresses with apartment/lot numbers. Order:
        1. ``region_sido + region_sigungu`` (e.g. "강원 평창군")  ← preferred
        2. ``region_sigungu`` alone
        3. ``address`` (full address; works only for clean real addresses)
        4. camp name as last resort
    """
    sido = (payload.get("region_sido") or "").strip()
    sigungu = (payload.get("region_sigungu") or "").strip()
    region = " ".join(filter(None, [sido, sigungu])).strip()
    if region:
        return region
    if sigungu:
        return sigungu
    addr = (payload.get("address") or "").strip()
    if addr:
        return addr
    return (payload.get("name") or payload.get("id", "")).strip()


def _camp_lookup(ids: list[str]) -> dict[str, dict]:
    """Resolve camp ids → row payload via FalkorDB KG.

    # T37: TODO enrich with PG row-store data (GetSiteDetail use-case).
    """
    out: dict[str, dict] = {}
    try:
        g = _falkor()
        for cid in ids:
            rs = g.query(
                "MATCH (c:Camp {id: $id})-[:LOCATED_IN]->(r:Region) "
                "RETURN c.id, c.name, r.sido, r.sigungu, c.address, c.lat, c.lon",
                params={"id": cid},
            ).result_set
            if rs:
                row = rs[0]
                out[cid] = {
                    "id": row[0], "name": row[1],
                    "region_sido": row[2], "region_sigungu": row[3],
                    "address": row[4], "lat": row[5], "lon": row[6],
                }
    except Exception:
        pass
    return out


@app.get("/eta")
async def eta_one(
    origin: str = Query(..., description="출발지 (지명 텍스트)"),
    dest: str = Query(..., description="도착지 (지명 텍스트)"),
    timeout_s: float = Query(12.0, ge=2.0, le=60.0),
) -> dict:
    """단건 ETA — 두 지명 간 차량 추천 루트 분 단위 시간."""
    client = _get_etago()
    r = await client.fetch(origin, dest, timeout_s)
    return r.to_dict()


class EtaBatchRequest(BaseModel):
    origin: str = Field(..., description="출발지 지명")
    ids: list[str] = Field(..., min_length=1, max_length=500)
    max_minutes: Optional[int] = Field(None, ge=1, le=1440, description="최대 시간 분(이내만 within=true)")
    concurrency: int = Field(4, ge=1, le=12)
    timeout_s: float = Field(12.0, ge=2.0, le=60.0)


@app.post("/eta/batch")
async def eta_batch(req: EtaBatchRequest) -> dict:
    """일괄 ETA — 캠프 id 리스트에 대해 origin 으로부터 차량 ETA 계산.

    응답:
        {
          "origin": "강남역",
          "max_minutes": 90,
          "checked": 30,
          "within_count": 7,
          "results": [
            {"id":"mock-001","minutes":58,"source":"kakao","within":true,"place":"경기 가평군"},
            {"id":"mock-002","minutes":146,"within":false,...},
            ...
          ]
        }
    """
    client = _get_etago()
    rows = _camp_lookup(req.ids)
    pairs: list[tuple[str, str]] = []
    place_for: dict[str, str] = {}
    for cid in req.ids:
        if cid not in rows:
            continue
        place = _place_for_camp(rows[cid])
        if not place:
            continue
        pairs.append((cid, place))
        place_for[cid] = place

    raw = await client.fetch_many(req.origin, pairs, concurrency=req.concurrency, timeout_s=req.timeout_s)

    results: list[dict] = []
    within = 0
    for cid in req.ids:
        if cid not in raw:
            results.append({"id": cid, "minutes": None, "error": "no place name", "within": False})
            continue
        r = raw[cid]
        ok = r.minutes is not None and (req.max_minutes is None or r.minutes <= req.max_minutes)
        if ok:
            within += 1
        results.append({
            "id": cid,
            "minutes": r.minutes,
            "source": r.source,
            "error": r.error,
            "place": place_for.get(cid),
            "within": ok,
        })

    return {
        "origin": req.origin,
        "max_minutes": req.max_minutes,
        "checked": len(results),
        "within_count": within,
        "results": results,
    }


@app.delete("/eta/cache")
def eta_cache_clear() -> dict:
    """ETA 메모리 캐시 비우기 (origin 변경 시 재산정 용)."""
    global _etago
    if _etago is not None:
        _etago.clear_cache()
    return {"cleared": True}


# ─────────────────────────────────────────────────────────────────────────
# /graph/* — generic graph view endpoints (Cytoscape elements format)
#
# Spec is intentionally open — labels/edge-types are discovered at runtime
# (CALL db.labels / db.relationshipTypes), node payloads are returned as
# `properties(n)` maps so the FE can dump unknown shapes generically.
# Natural keys for synthetic Cytoscape ids are looked up per-label; unknown
# labels fall back to `id` then first property key.
# ─────────────────────────────────────────────────────────────────────────

# Composite primary keys per known label. Unknown labels fall back to
# `_pick_natural_key(props)` which scans common id-ish keys.
PRIMARY_KEY: dict[str, tuple[str, ...]] = {
    "Camp": ("id",),
    "Region": ("sido", "sigungu"),
    "Category": ("name",),
    "Facility": ("name",),
}


def _pick_natural_key(props: dict) -> str:
    """Pick a stable natural key from a node's properties dict.

    Tries: id → name → title → first non-empty scalar.
    """
    for k in ("id", "name", "title", "key"):
        v = props.get(k)
        if v is not None and v != "":
            return str(v)
    for k, v in props.items():
        if v is not None and v != "" and not isinstance(v, (list, dict)):
            return f"{k}={v}"
    return ""


def _node_id(label: str, props: dict) -> str:
    keys = PRIMARY_KEY.get(label)
    if keys:
        parts = [str(props.get(k, "")) for k in keys]
        natural = "|".join(p for p in parts if p) or _pick_natural_key(props)
    else:
        natural = _pick_natural_key(props)
    return f"{label}:{natural}" if natural else f"{label}:?"


def _node_element(label: str, props: dict) -> dict:
    return {
        "data": {
            "id": _node_id(label, props),
            "label": label,
            "props": props or {},
        }
    }


def _edge_element(rtype: str, src: dict, dst: dict, src_label: str, dst_label: str, idx: int) -> dict:
    return {
        "data": {
            "id": f"e:{idx}:{rtype}",
            "source": _node_id(src_label, src),
            "target": _node_id(dst_label, dst),
            "label": rtype,
        }
    }


def _empty_graph(warning: str | None = None) -> JSONResponse:
    headers = {"X-Warning": warning} if warning else None
    return JSONResponse({"nodes": [], "edges": []}, status_code=200, headers=headers)


@app.get("/graph/schema")
def graph_schema() -> dict:
    """Discover labels, edge types, per-label sample property keys, and counts.

    Response:
        {
          "labels": [{"name": "Camp", "count": 2934, "keys": ["id", "name", "lat", ...]}],
          "edges":  [{"name": "LOCATED_IN", "count": 2934}, ...]
        }
    """
    out = {"labels": [], "edges": []}
    try:
        g = _falkor()
        rs = g.query("CALL db.labels()").result_set
        labels = [r[0] for r in rs if r and r[0]]
        rs = g.query("CALL db.relationshipTypes()").result_set
        rel_types = [r[0] for r in rs if r and r[0]]

        for lbl in labels:
            try:
                cnt_rs = g.query(f"MATCH (n:`{lbl}`) RETURN count(n)").result_set
                count = int(cnt_rs[0][0]) if cnt_rs else 0
            except Exception:
                count = 0
            keys: set[str] = set()
            try:
                kr = g.query(f"MATCH (n:`{lbl}`) RETURN keys(n) LIMIT 8").result_set
                for row in kr:
                    for k in (row[0] or []):
                        keys.add(k)
            except Exception:
                pass
            out["labels"].append({"name": lbl, "count": count, "keys": sorted(keys)})

        for rt in rel_types:
            try:
                cr = g.query(f"MATCH ()-[r:`{rt}`]->() RETURN count(r)").result_set
                count = int(cr[0][0]) if cr else 0
            except Exception:
                count = 0
            out["edges"].append({"name": rt, "count": count})
    except Exception as e:
        return JSONResponse(out, status_code=200, headers={"X-Warning": f"falkor: {type(e).__name__}"})
    return out


def _parse_labels(labels: Optional[str]) -> list[str]:
    if not labels:
        return []
    return [s.strip() for s in labels.split(",") if s.strip()]


def _parse_node_id(node_id: str) -> tuple[str, str]:
    """`Camp:abc` → (`Camp`, `abc`). `Region:강원|평창군` → (`Region`, `강원|평창군`)."""
    if ":" not in node_id:
        return ("", node_id)
    label, _, natural = node_id.partition(":")
    return (label, natural)


def _where_for_natural_key(label: str, natural: str, alias: str = "n") -> tuple[str, dict]:
    """Build a WHERE clause + params binding `alias` to the node identified by natural key."""
    keys = PRIMARY_KEY.get(label)
    params: dict = {}
    if keys and len(keys) > 1:
        parts = natural.split("|")
        # Pad/truncate to expected arity.
        parts = (parts + [""] * len(keys))[: len(keys)]
        clauses = []
        for i, k in enumerate(keys):
            params[f"k_{k}"] = parts[i]
            clauses.append(f"{alias}.`{k}` = $k_{k}")
        return (" AND ".join(clauses), params)
    if keys and len(keys) == 1:
        k = keys[0]
        params[f"k_{k}"] = natural
        return (f"{alias}.`{k}` = $k_{k}", params)
    # Unknown label — try id first, fall back to name.
    params["k_id"] = natural
    return (f"({alias}.id = $k_id OR {alias}.name = $k_id)", params)


def _primary_text_key(label: str) -> str:
    """Best textual property to search/display for a label."""
    keys = PRIMARY_KEY.get(label)
    if keys:
        # Last key in composite is usually the most descriptive (e.g. sigungu over sido).
        return keys[-1]
    return "name"


@app.get("/graph/sample")
def graph_sample(
    labels: Optional[str] = Query(None, description="comma-separated label filter; empty = all"),
    limit: int = Query(200, ge=1, le=2000),
) -> dict:
    """Seed graph — first $limit (node, edge, neighbor) tuples where the
    primary node matches the label filter (or any label if unfiltered).

    Note on Cypher pattern: FalkorDB has a quirk where ``MATCH (n) WITH n
    LIMIT k OPTIONAL MATCH (n)-[r]-(m)`` only returns one row per `n` even
    when n has multiple neighbors — so we MATCH the (n,r,m) tuples directly
    and LIMIT at the RETURN, which gives proper edge expansion.

    Edges are deduplicated by (source_id, target_id, rel_type) as a safety
    net (FalkorDB currently returns each undirected edge once, but the dedup
    keeps the contract stable across versions).
    """
    label_list = _parse_labels(labels)
    try:
        g = _falkor()
        if label_list:
            cy = (
                "MATCH (n)-[r]-(m) WHERE labels(n)[0] IN $labels "
                "RETURN labels(n)[0] AS l_n, properties(n) AS p_n, "
                "       type(r) AS r_t, "
                "       CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END AS r_dir, "
                "       labels(m)[0] AS l_m, properties(m) AS p_m "
                "LIMIT $limit"
            )
            params = {"labels": label_list, "limit": limit}
        else:
            cy = (
                "MATCH (n)-[r]-(m) "
                "RETURN labels(n)[0] AS l_n, properties(n) AS p_n, "
                "       type(r) AS r_t, "
                "       CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END AS r_dir, "
                "       labels(m)[0] AS l_m, properties(m) AS p_m "
                "LIMIT $limit"
            )
            params = {"limit": limit}
        rs = g.query(cy, params=params).result_set
    except Exception as e:
        return _empty_graph(f"falkor: {type(e).__name__}")

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    edge_seen: set[tuple[str, str, str]] = set()
    for row in rs:
        l_n, p_n, r_t, r_dir, l_m, p_m = row
        if l_n:
            el = _node_element(l_n, p_n or {})
            nodes[el["data"]["id"]] = el
        if l_m:
            el = _node_element(l_m, p_m or {})
            nodes[el["data"]["id"]] = el
        if r_t and l_n and l_m:
            if r_dir == "out":
                src_label, src_props, dst_label, dst_props = l_n, p_n or {}, l_m, p_m or {}
            else:
                src_label, src_props, dst_label, dst_props = l_m, p_m or {}, l_n, p_n or {}
            src_id = _node_id(src_label, src_props)
            dst_id = _node_id(dst_label, dst_props)
            key = (src_id, dst_id, r_t)
            if key in edge_seen:
                continue
            edge_seen.add(key)
            edges.append(_edge_element(r_t, src_props, dst_props, src_label, dst_label, len(edges)))
    return {"nodes": list(nodes.values()), "edges": edges}


@app.get("/graph/expand")
def graph_expand(
    id: str = Query(..., description="cytoscape node id, e.g. 'Camp:abc'"),
    direction: str = Query("both", pattern="^(in|out|both)$"),
    limit: int = Query(60, ge=1, le=500),
) -> dict:
    """Fetch neighbors of one node (by synthetic id). Returns the source node + neighbors + edges."""
    label, natural = _parse_node_id(id)
    if not label or not natural:
        return _empty_graph("invalid id")
    where, params = _where_for_natural_key(label, natural, alias="n")
    params["limit"] = limit

    if direction == "out":
        rel = "-[r]->"
    elif direction == "in":
        rel = "<-[r]-"
    else:
        rel = "-[r]-"

    cy = (
        f"MATCH (n:`{label}`) WHERE {where} "
        f"OPTIONAL MATCH (n){rel}(m) "
        "RETURN labels(n)[0] AS l_n, properties(n) AS p_n, "
        "       type(r) AS r_t, "
        "       CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END AS r_dir, "
        "       labels(m)[0] AS l_m, properties(m) AS p_m "
        "LIMIT $limit"
    )
    try:
        rs = _falkor().query(cy, params=params).result_set
    except Exception as e:
        return _empty_graph(f"falkor: {type(e).__name__}")

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for i, row in enumerate(rs):
        l_n, p_n, r_t, r_dir, l_m, p_m = row
        if l_n:
            el = _node_element(l_n, p_n or {})
            nodes[el["data"]["id"]] = el
        if l_m:
            el = _node_element(l_m, p_m or {})
            nodes[el["data"]["id"]] = el
        if r_t and l_n and l_m:
            if r_dir == "out":
                edges.append(_edge_element(r_t, p_n or {}, p_m or {}, l_n, l_m, i))
            else:
                edges.append(_edge_element(r_t, p_m or {}, p_n or {}, l_m, l_n, i))
    return {"nodes": list(nodes.values()), "edges": edges}


@app.get("/graph/search")
def graph_search(
    q: str = Query(..., min_length=1),
    label: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Text-search nodes by primary text property (CONTAINS). Returns matches as cytoscape nodes."""
    try:
        g = _falkor()
        if label:
            text_key = _primary_text_key(label)
            cy = (
                f"MATCH (n:`{label}`) "
                f"WHERE n.`{text_key}` CONTAINS $q "
                "RETURN labels(n)[0] AS l_n, properties(n) AS p_n LIMIT $limit"
            )
            rs = g.query(cy, params={"q": q, "limit": limit}).result_set
        else:
            # Search across known + discovered labels using each label's primary text key.
            try:
                lr = g.query("CALL db.labels()").result_set
                all_labels = [r[0] for r in lr if r and r[0]]
            except Exception:
                all_labels = list(PRIMARY_KEY.keys())
            rs = []
            per = max(1, limit // max(1, len(all_labels)))
            for lbl in all_labels:
                tk = _primary_text_key(lbl)
                try:
                    sub = g.query(
                        f"MATCH (n:`{lbl}`) WHERE n.`{tk}` CONTAINS $q "
                        f"RETURN labels(n)[0], properties(n) LIMIT {per}",
                        params={"q": q},
                    ).result_set
                    rs.extend(sub)
                except Exception:
                    continue
                if len(rs) >= limit:
                    break
            rs = rs[:limit]
    except Exception as e:
        return _empty_graph(f"falkor: {type(e).__name__}")

    nodes: dict[str, dict] = {}
    for row in rs:
        l_n, p_n = row[0], row[1]
        if l_n:
            el = _node_element(l_n, p_n or {})
            nodes[el["data"]["id"]] = el
    return {"nodes": list(nodes.values()), "edges": []}


# Mount fe/ static dir at /  — serves index.html.
fe_path = Path(FE_DIR)
if fe_path.is_dir():
    app.mount("/", StaticFiles(directory=str(fe_path), html=True), name="fe")
