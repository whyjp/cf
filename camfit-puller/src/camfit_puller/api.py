"""FastAPI read API consumed by fe/index.html.

All handlers depend on `Container` (composition root) — never on concrete
adapters. PG is the truth; FalkorDB is the derived graph; semantic search uses
pgvector.

RocksDB removed in T36. ROCKS_BASE / camp:* / detail:* / reviews:* keys gone.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .settings import Settings
from .container import Container
from .domain.errors import CampNotFound


_settings = Settings()
_container = Container(_settings)


def _falkor():
    """Return a raw FalkorDB graph handle.

    Kept as a module-level function so tests can monkeypatch it directly
    (``monkeypatch.setattr(api_mod, "_falkor", lambda: fake)``).  All
    /graph/* route handlers call this instead of _container.graph so the
    existing test suite works without changes.
    """
    return _container.graph._g()


app = FastAPI(title="camfit-puller API (P2)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# ───────────────────────── Health ─────────────────────────

@app.get("/healthz")
def healthz() -> dict:
    status: dict[str, str] = {
        "postgres": "down",
        "falkor": "down",
        "embedder": "down",
        "etago": "down",
        "geocoder": "down",
    }
    try:
        _container.camps_read.count()
        status["postgres"] = "up"
    except Exception:
        pass
    try:
        if _container.graph.healthcheck():
            status["falkor"] = "up"
    except Exception:
        pass
    try:
        # Just confirm the property is reachable; don't load the model on every healthz.
        # The property is cached after first access.
        embedder_name = _settings.embedder
        status["embedder"] = embedder_name
    except Exception:
        pass
    try:
        from .adapters.eta.etago_subprocess import EtagoSubprocessProvider
        EtagoSubprocessProvider()  # raises if binary missing
        status["etago"] = "up"
    except Exception:
        pass
    try:
        # geocoder is lazy; just verify config
        status["geocoder"] = _settings.geocoder
    except Exception:
        pass
    return status


# ───────────────────────── Sites (list / detail / search) ────────────────

@app.get("/sites/search")
def site_search(q: str = Query(..., min_length=1), k: int = 20) -> list[dict]:
    """Semantic search over camp embeddings."""
    if not q.strip():
        return []
    camps = _container.semantic_search().execute(q.strip(), k=max(1, min(k, 100)))
    return [_camp_to_fe_row(c) for c in camps]


@app.get("/sites/{site_id}/similar")
def site_similar(site_id: str, k: int = 10) -> list[dict]:
    """KNN nearest-neighbor camps to the given camp."""
    vec = _container.vector.get(site_id)
    if vec is None:
        raise HTTPException(404, f"no embedding for camp {site_id}; run BuildEmbeddings first")
    hits = _container.vector.knn(vec, k=k + 1)  # +1 to exclude self
    other_ids = [cid for cid, _ in hits if cid != site_id][:k]
    by_id = {c.id: c for c in _container.camps_read.list_filtered(ids=other_ids)}
    return [_camp_to_fe_row(by_id[cid]) for cid in other_ids if cid in by_id]


@app.get("/sites/{site_id}")
def site_detail(site_id: str) -> dict:
    try:
        d = _container.get_site_detail().execute(site_id)
    except CampNotFound:
        raise HTTPException(404, f"camp not found: {site_id}")
    # FE DetailPanel reads flat camelCase + flat region/geo. Project here so
    # the use-case stays canonical (Camp domain shape) while the FE stays terse.
    camp = d.get("camp") or {}
    geo = camp.get("geo") or {}
    region = camp.get("region") or {}
    photos = camp.get("photos") or []
    flat = {
        "id": camp.get("id"),
        "name": camp.get("name"),
        "address": camp.get("address"),
        "lat": geo.get("lat"),
        "lon": geo.get("lon"),
        "region_sido": region.get("sido"),
        "region_sigungu": region.get("sigungu"),
        "categories": list(camp.get("collections") or []) + list(camp.get("types") or []),
        "facilities": list(camp.get("facilities") or []) + list(camp.get("additional_facilities") or []),
        "hashtags": camp.get("hashtags") or [],
        "description": camp.get("description"),
        "brief": camp.get("brief"),
        "locationBrief": camp.get("location_brief"),
        "contact": camp.get("contact"),
        "priceStartFrom": camp.get("price_start_from"),
        "priceEndTo": camp.get("price_end_to"),
        "numOfReviews": camp.get("num_of_reviews"),
        "bookmarkCount": camp.get("bookmark_count"),
        "url": camp.get("url"),
        "photos": [
            {"url": p.get("url"), "thumb": p.get("thumb_url") or p.get("url")}
            for p in photos
        ],
        "reviews_total": d.get("reviews_total"),
        "reviews_top": [
            {
                "user": r.get("user_nick"),
                "season": r.get("season"),
                "userType": r.get("user_type"),
                "numOfDays": r.get("num_of_days"),
                "score": r.get("score"),
                "text": r.get("text"),
            }
            for r in (d.get("reviews_top") or [])
        ],
        "concepts": d.get("concepts") or [],
        "theme": d.get("theme"),
    }
    return flat


def _camp_to_fe_row(c) -> dict:
    """FE-friendly flat projection of a Camp domain model.

    The map view in fe/index.html reads `r.lat`/`r.lon`/`r.sido` directly
    (no `.geo.lat` traversal), and the chip rendering iterates `r.categories`.

    The legacy boolean axis flags `has_valley`/`has_kids`/`has_trampoline` are
    derived by checking, in priority order:
      1. `location_types` (camfit's structured terrain tag — `valley`/`mountain`/...)
      2. `facilities` and `additional_facilities` (English codes — `trampoline`/`swimmingPool`/...)
      3. `collections` + `types` (Korean editorial buckets — `콜렉션:키즈캠핑장`)
      4. `hashtags` (free-form — `계곡캠핑장`/`키즈캠핑장`)

    A keyword that appears as either its English code (in (1)/(2)) OR its
    Korean variant (in (3)/(4)) lights up the flag. False-positive risk is
    accepted; the polarity-aware `/sites?concept=kids` will eventually
    supersede these flags.
    """
    geo = c.geo
    region = c.region
    cats = list(c.collections or [])
    facs = list(c.facilities or []) + list(c.additional_facilities or [])
    types = list(c.types or [])
    location_types = list(c.location_types or [])
    hashtags = list(c.hashtags or [])

    # Search corpus for the boolean axis flags — every meaningful tag source
    # joined into one lowercased blob for substring matching.
    haystack = " ".join(cats + types + facs + location_types + hashtags).lower()

    def _matches(*needles: str) -> bool:
        return any(n.lower() in haystack for n in needles)

    return {
        "id": c.id,
        "name": c.name,
        "sido": region.sido if region else None,
        "sigungu": region.sigungu if region else None,
        "address": c.address,
        "lat": geo.lat if geo else None,
        "lon": geo.lon if geo else None,
        # `categories` is the chip-display source. Drop opaque exhibition IDs
        # (전시:E* — camfit's editorial bucket count >500 each, no semantic
        # value) so the FE collection chip row surfaces meaningful tags only.
        "categories": [s for s in (cats + types) if not s.startswith("전시:")],
        "facilities": facs,
        "location_types": location_types,
        "hashtags": hashtags,
        "has_valley": _matches("valley", "계곡"),
        "has_kids": _matches("kids", "키즈", "아이"),
        "has_trampoline": _matches("trampoline", "트램펄린", "트램폴린"),
        "num_of_reviews": c.num_of_reviews,
        "bookmark_count": c.bookmark_count,
        "url": c.url,
    }


@app.get("/sites")
def sites(
    region: Optional[str] = None,
    sigungu: Optional[str] = None,
    concept: Optional[list[str]] = Query(None, description="AND of concepts (repeat ?concept=)"),
    concepts_any: Optional[str] = Query(None, description="OR of concepts (comma-separated)"),
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    bbox: Optional[str] = Query(None, description="lon1,lat1,lon2,lat2"),
    limit: int = 2000,
) -> list[dict]:
    bb: Optional[tuple[float, float, float, float]] = None
    if bbox:
        try:
            parts = [float(x) for x in bbox.split(",")]
            if len(parts) == 4:
                bb = (parts[0], parts[1], parts[2], parts[3])
        except ValueError:
            pass
    any_list = [s.strip() for s in concepts_any.split(",")] if concepts_any else None
    rows = _container.camps_read.list_filtered(
        sido=region, sigungu=sigungu,
        concept=concept, concepts_any=any_list,
        min_score=min_score, max_score=max_score,
        bbox=bb, limit=limit,
    )
    return [_camp_to_fe_row(c) for c in rows]


# ───────────────────────── Facets ─────────────────────────

@app.get("/facets")
def facets() -> dict:
    """Returns regions/concepts/themes counts. Read from PG (source of truth).

    `axis` concepts (with `is_axis=true`) are surfaced separately for FE
    primary toggles vs the long tail of dynamic concept chips.
    """
    out: dict = {"regions": [], "concept_axes": [], "concepts": [], "themes": []}
    try:
        # Region buckets: distinct (sido, sigungu) with counts.
        with _container._pg.conn() as c, c.cursor() as cur:
            cur.execute("""
                SELECT sido, sigungu, count(*) FROM camps
                WHERE sido IS NOT NULL GROUP BY sido, sigungu ORDER BY count(*) DESC
            """)
            out["regions"] = [{"sido": r[0], "sigungu": r[1], "count": int(r[2])} for r in cur.fetchall()]

            # Concept axis vs non-axis (with PG matview backing camp counts)
            cur.execute("""
                SELECT c.id, c.name, c.category, c.is_axis,
                       (SELECT count(*) FROM camp_concept_aggregated agg
                        WHERE agg.concept_id = c.id AND agg.final_score > 0) AS n
                FROM concepts c
                ORDER BY n DESC NULLS LAST
            """)
            for r in cur.fetchall():
                bucket = "concept_axes" if r[3] else "concepts"
                out[bucket].append({
                    "id": r[0], "name": r[1], "category": r[2],
                    "is_axis": bool(r[3]), "count": int(r[4] or 0),
                })

        for theme in _container.theme_repo.all():
            out["themes"].append({
                "id": theme.id, "label": theme.label,
                "count": theme.member_count, "manual_label": theme.manual_label,
            })
    except Exception as e:
        return JSONResponse(out, status_code=200, headers={"X-Warning": f"facets: {type(e).__name__}: {e}"})
    return out


# ───────────────────────── Concepts / Themes ────────────────────

@app.get("/concepts")
def concepts() -> list[dict]:
    return [c.model_dump() for c in _container.concept_repo.all()]


@app.get("/concepts/{name}/camps")
def concept_camps(name: str, min_score: float = 0.3, limit: int = 200) -> list[dict]:
    rows = _container.camps_read.list_filtered(
        concept=[name], min_score=min_score, limit=limit,
    )
    return [c.model_dump() for c in rows]


@app.get("/themes")
def themes() -> list[dict]:
    return [
        {"id": t.id, "label": t.label, "count": t.member_count, "manual_label": t.manual_label}
        for t in _container.theme_repo.all()
    ]


@app.get("/themes/{theme_id}/camps")
def theme_camps(theme_id: str, limit: int = 200) -> list[dict]:
    with _container._pg.conn() as c, c.cursor() as cur:
        cur.execute("SELECT camp_id FROM camp_themes WHERE theme_id=%s LIMIT %s", (theme_id, limit))
        ids = [r[0] for r in cur.fetchall()]
    if not ids:
        return []
    rows = _container.camps_read.list_filtered(ids=ids, limit=limit)
    return [c.model_dump() for c in rows]


# ───────────────────────── Marks ─────────────────────────

@app.get("/marks")
def list_marks() -> dict:
    """Lists all axes with mark counts + sample top scorer per axis."""
    axes = _container.mark_repo.all_axes()
    out: list[dict] = []
    for axis, count in axes:
        top = _container.mark_repo.for_axis(axis, min_level="exceptional", limit=3)
        out.append({"axis": axis, "count": count,
                    "top": [{"camp_id": m.camp_id, "level": m.level, "score": m.score} for m in top]})
    return {"axes": out}


@app.get("/marks/{axis}/camps")
def axis_camps(axis: str, min_level: Optional[str] = None, limit: int = 100) -> list[dict]:
    marks = _container.mark_repo.for_axis(axis, min_level=min_level, limit=limit)
    return [m.model_dump() for m in marks]


# ───────────────────────── ETA ─────────────────────────

class EtaBatchRequest(BaseModel):
    origin: str = Field(..., min_length=1)
    # 10k cap — the FE sends every camp in the current filtered view (1,656
    # at full crawl, soon to grow). The eta_cache PG layer makes repeat calls
    # cheap; concurrency caps at 12 to avoid hammering the etago subprocess.
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
    r = _container.eta.drive_eta(origin, dest, timeout_s=timeout_s)
    return r.model_dump()


@app.post("/eta/batch")
def eta_batch(req: EtaBatchRequest) -> dict:
    return _container.eta_for_fleet().execute(
        req.origin, req.ids,
        max_minutes=req.max_minutes,
        concurrency=req.concurrency,
        timeout_s=req.timeout_s,
    )


@app.delete("/eta/cache")
def eta_cache_clear() -> dict:
    n = _container.eta_cache.clear()
    return {"cleared": int(n)}


# ───────────────────────── Admin (P2 pipeline triggers) ────────────

@app.post("/admin/rebuild-graph")
def rebuild_graph() -> dict:
    return _container.rebuild_graph().execute()


@app.post("/admin/reembed")
def reembed() -> dict:
    n = _container.build_embeddings().execute()
    return {"camps_embedded": n}


# ─────────────────────────────────────────────────────────────────────────
# /graph/* — generic graph view endpoints (Cytoscape elements format)
#
# Spec is intentionally open — labels/edge-types are discovered at runtime
# (CALL db.labels / db.relationshipTypes), node payloads are returned as
# `properties(n)` maps so the FE can dump unknown shapes generically.
# Natural keys for synthetic Cytoscape ids are looked up per-label; unknown
# labels fall back to `_pick_natural_key(props)` which scans common id-ish keys.
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
    out: dict[str, list] = {"labels": [], "edges": []}
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
    limit: int = Query(200, ge=1, le=100000),
    sido: Optional[str] = Query(None, description="filter Camps to this sido (region anchor)"),
    sigungu: Optional[str] = Query(None, description="filter Camps to this sigungu"),
    concept: Optional[str] = Query(None, description="filter Camps that have a HAS_CATEGORY|HAS_FACILITY edge to a node with name=$concept"),
    eta_origin: Optional[str] = Query(None, description="ETA origin (e.g. '강남역'); resolved per Camp"),
    eta_max_minutes: Optional[int] = Query(None, ge=1, le=1440, description="drop Camp nodes whose drive ETA exceeds this"),
) -> dict:
    """Seed graph — first $limit (node, edge, neighbor) tuples where the
    primary node matches the label filter (or any label if unfiltered).

    When any of `sido`/`sigungu`/`concept` are present, the query becomes
    Camp-anchored: pick `$limit` Camps satisfying the filters, then expand
    their full neighborhoods. When unfiltered, the legacy pattern is used.

    When `eta_origin` + `eta_max_minutes` are both present, Camp nodes are
    additionally pruned post-query: each Camp is resolved to its drive ETA
    (using its address/sido+sigungu+name) and dropped if minutes exceed the
    cap. Camps without lat/lon (no place name resolvable) are also dropped.
    Edges adjacent to dropped Camps are dropped too.

    Edges are deduplicated by (source_id, target_id, rel_type) as a safety
    net (FalkorDB currently returns each undirected edge once, but the dedup
    keeps the contract stable across versions).
    """
    label_list = _parse_labels(labels)
    has_camp_filter = bool(sido or sigungu or concept)
    try:
        g = _falkor()
        if has_camp_filter:
            # Camp-anchored: collect Camps matching all provided sub-filters,
            # LIMIT to $limit, then expand neighborhoods.
            where_clauses: list[str] = []
            params: dict[str, Any] = {"limit": limit}
            extra_match: list[str] = []
            if sido or sigungu:
                extra_match.append("MATCH (c)-[:LOCATED_IN]->(reg:Region)")
                if sido:
                    where_clauses.append("reg.sido = $sido")
                    params["sido"] = sido
                if sigungu:
                    where_clauses.append("reg.sigungu = $sigungu")
                    params["sigungu"] = sigungu
            if concept:
                extra_match.append("MATCH (c)-[:HAS_CATEGORY|HAS_FACILITY]->(con)")
                where_clauses.append("con.name = $concept")
                params["concept"] = concept
            where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            cy = (
                "MATCH (c:Camp) "
                + " ".join(extra_match)
                + where
                + " WITH DISTINCT c LIMIT $limit "
                "OPTIONAL MATCH (c)-[r]-(m) "
                "RETURN labels(c)[0] AS l_n, properties(c) AS p_n, "
                "       type(r) AS r_t, "
                "       CASE WHEN startNode(r) = c THEN 'out' ELSE 'in' END AS r_dir, "
                "       labels(m)[0] AS l_m, properties(m) AS p_m"
            )
            rs = g.query(cy, params=params).result_set
        elif label_list:
            cy = (
                "MATCH (n)-[r]-(m) WHERE labels(n)[0] IN $labels "
                "RETURN labels(n)[0] AS l_n, properties(n) AS p_n, "
                "       type(r) AS r_t, "
                "       CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END AS r_dir, "
                "       labels(m)[0] AS l_m, properties(m) AS p_m "
                "LIMIT $limit"
            )
            params = {"labels": label_list, "limit": limit}
            rs = g.query(cy, params=params).result_set
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

    # ETA filter (post-query): drop Camp ids exceeding the budget.
    eta_keep: Optional[set[str]] = None
    eta_warning: Optional[str] = None
    if eta_origin and eta_max_minutes is not None:
        try:
            camp_props_by_id: dict[str, dict] = {}
            for row in rs:
                l_n, p_n, _r_t, _r_dir, l_m, p_m = row
                if l_n == "Camp" and p_n:
                    cid = p_n.get("id")
                    if cid:
                        camp_props_by_id[str(cid)] = p_n
                if l_m == "Camp" and p_m:
                    cid = p_m.get("id")
                    if cid:
                        camp_props_by_id[str(cid)] = p_m

            keep: set[str] = set()
            if camp_props_by_id:
                # Build place names from Camp props (mirrors EtaForFleet._place_for):
                # prefer "sido sigungu", fall back to address, then name.
                pairs: list[tuple[str, str]] = []
                for cid, props in camp_props_by_id.items():
                    sido_p = (props.get("sido") or "").strip()
                    sigungu_p = (props.get("sigungu") or "").strip()
                    region = " ".join(filter(None, [sido_p, sigungu_p])).strip()
                    place: Optional[str] = None
                    if region and "(미지정)" not in region:
                        place = region
                    elif (props.get("address") or "").strip():
                        place = props["address"].strip()
                    elif (props.get("name") or "").strip():
                        place = props["name"].strip()
                    # Camps with no resolvable place + no lat/lon: drop.
                    if place and (props.get("lat") is not None and props.get("lon") is not None):
                        pairs.append((cid, place))
                if pairs:
                    raw = _container.eta.drive_eta_batch(
                        eta_origin, pairs, concurrency=4, timeout_s=12.0,
                    )
                    for cid, r in raw.items():
                        if r.minutes is not None and r.minutes <= eta_max_minutes:
                            keep.add(cid)
            eta_keep = keep
        except Exception as e:
            # Non-fatal: surface as warning, leave eta_keep=None (no filtering).
            eta_warning = f"eta: {type(e).__name__}: {e}"
            eta_keep = None

    def _camp_dropped(label: str, props: dict) -> bool:
        if eta_keep is None:
            return False
        if label != "Camp":
            return False
        cid = (props or {}).get("id")
        return str(cid) not in eta_keep if cid is not None else True

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    edge_seen: set[tuple[str, str, str]] = set()
    for row in rs:
        l_n, p_n, r_t, r_dir, l_m, p_m = row
        n_drop = _camp_dropped(l_n, p_n or {})
        m_drop = _camp_dropped(l_m, p_m or {}) if l_m else False
        if l_n and not n_drop:
            el = _node_element(l_n, p_n or {})
            nodes[el["data"]["id"]] = el
        if l_m and not m_drop:
            el = _node_element(l_m, p_m or {})
            nodes[el["data"]["id"]] = el
        if r_t and l_n and l_m and not n_drop and not m_drop:
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
    headers = {"X-Warning": eta_warning} if eta_warning else None
    body = {"nodes": list(nodes.values()), "edges": edges}
    if headers:
        return JSONResponse(body, status_code=200, headers=headers)
    return body


@app.get("/graph/expand")
def graph_expand(
    id: str = Query(..., description="cytoscape node id, e.g. 'Camp:abc'"),
    direction: str = Query("both", pattern="^(in|out|both)$"),
    limit: int = Query(60, ge=1, le=500),
    eta_origin: Optional[str] = Query(None, description="ETA origin (e.g. '강남역'); resolved per Camp neighbor"),
    eta_max_minutes: Optional[int] = Query(None, ge=1, le=1440, description="drop Camp neighbors whose drive ETA exceeds this"),
) -> dict:
    """Fetch neighbors of one node (by synthetic id). Returns the source node + neighbors + edges.

    Optional `eta_origin`+`eta_max_minutes` filters Camp neighbors post-query
    (same semantic as /graph/sample).
    """
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

    # ETA filter (post-query): drop Camp ids exceeding budget. Same logic as /graph/sample.
    eta_keep: Optional[set[str]] = None
    eta_warning: Optional[str] = None
    if eta_origin and eta_max_minutes is not None:
        try:
            camp_props_by_id: dict[str, dict] = {}
            for row in rs:
                l_n, p_n, _r_t, _r_dir, l_m, p_m = row
                if l_n == "Camp" and p_n:
                    cid = p_n.get("id")
                    if cid:
                        camp_props_by_id[str(cid)] = p_n
                if l_m == "Camp" and p_m:
                    cid = p_m.get("id")
                    if cid:
                        camp_props_by_id[str(cid)] = p_m
            keep: set[str] = set()
            if camp_props_by_id:
                pairs: list[tuple[str, str]] = []
                for cid, props in camp_props_by_id.items():
                    sido_p = (props.get("sido") or "").strip()
                    sigungu_p = (props.get("sigungu") or "").strip()
                    region = " ".join(filter(None, [sido_p, sigungu_p])).strip()
                    place: Optional[str] = None
                    if region and "(미지정)" not in region:
                        place = region
                    elif (props.get("address") or "").strip():
                        place = props["address"].strip()
                    elif (props.get("name") or "").strip():
                        place = props["name"].strip()
                    if place and (props.get("lat") is not None and props.get("lon") is not None):
                        pairs.append((cid, place))
                if pairs:
                    raw = _container.eta.drive_eta_batch(
                        eta_origin, pairs, concurrency=4, timeout_s=12.0,
                    )
                    for cid, r in raw.items():
                        if r.minutes is not None and r.minutes <= eta_max_minutes:
                            keep.add(cid)
            eta_keep = keep
        except Exception as e:
            eta_warning = f"eta: {type(e).__name__}: {e}"
            eta_keep = None

    def _camp_dropped(lbl: str, props: dict) -> bool:
        if eta_keep is None:
            return False
        if lbl != "Camp":
            return False
        cid = (props or {}).get("id")
        return str(cid) not in eta_keep if cid is not None else True

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for i, row in enumerate(rs):
        l_n, p_n, r_t, r_dir, l_m, p_m = row
        n_drop = _camp_dropped(l_n, p_n or {})
        m_drop = _camp_dropped(l_m, p_m or {}) if l_m else False
        if l_n and not n_drop:
            el = _node_element(l_n, p_n or {})
            nodes[el["data"]["id"]] = el
        if l_m and not m_drop:
            el = _node_element(l_m, p_m or {})
            nodes[el["data"]["id"]] = el
        if r_t and l_n and l_m and not n_drop and not m_drop:
            if r_dir == "out":
                edges.append(_edge_element(r_t, p_n or {}, p_m or {}, l_n, l_m, i))
            else:
                edges.append(_edge_element(r_t, p_m or {}, p_n or {}, l_m, l_n, i))
    headers = {"X-Warning": eta_warning} if eta_warning else None
    body = {"nodes": list(nodes.values()), "edges": edges}
    if headers:
        return JSONResponse(body, status_code=200, headers=headers)
    return body


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


# ───────────────────────── FE static mount ─────────────────────

fe_path = _settings.fe_dir
if fe_path.is_dir():
    app.mount("/", StaticFiles(directory=str(fe_path), html=True), name="fe")
