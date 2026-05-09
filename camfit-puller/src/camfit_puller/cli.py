"""camfit-puller CLI — typer entry point.

Commands:
  crawl                 — legacy: cloakbrowser crawl → CSV (P1 utility, kept).
  serve                 — start FastAPI server (api.py).
  info                  — print version + healthz.
  pipeline run-all      — run full P2 pipeline (ingest → ... → rebuild-graph).
  pipeline <stage>      — run a single pipeline stage.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from . import __version__
from .crawler import CrawlConfig, crawl
from .csv_writer import write_rows
from .settings import Settings
from .container import Container

app = typer.Typer(help="camfit-puller — camfit.co.kr 폴라이트 크롤러 + 지식그래프/PG 적재 + FE serve")
pipeline_app = typer.Typer(help="P2 pipeline: ingest → vocab → embed → signals → themes → graph")
app.add_typer(pipeline_app, name="pipeline")
console = Console()


@app.callback()
def _root(version: bool = typer.Option(False, "--version", help="버전 출력")) -> None:
    if version:
        console.print(f"camfit-puller {__version__}")
        raise typer.Exit()


# ──────────────────────── Legacy: crawl + serve + info ────────────────────

@app.command(name="crawl")
def crawl_cmd(
    out: Path = typer.Option(Path("data/camfit.csv"), "--out", "-o", help="출력 CSV 경로"),
    page_size: int = typer.Option(50, help="페이지 크기"),
    max_pages: int = typer.Option(200, help="최대 페이지 수"),
    discover_only: bool = typer.Option(False, help="endpoint 만 확인하고 종료"),
) -> None:
    """camfit.co.kr 크롤 → CSV (P1 utility — for filling data/* archives)."""
    async def _run() -> int:
        cfg = CrawlConfig(page_size=page_size, max_pages=max_pages, discover_only=discover_only)
        recs = []
        async for r in crawl(cfg):
            recs.append(r)
        if discover_only:
            console.print("[discover] done — 0 row written")
            return 0
        n = write_rows(recs, out)
        console.print(f"[csv] {n} rows → {out}")
        return n
    asyncio.run(_run())


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="bind"),
    port: int = typer.Option(8070, help="포트"),
    reload: bool = typer.Option(False, help="dev reload"),
) -> None:
    """FE static + read API 서비스."""
    import uvicorn
    uvicorn.run("camfit_puller.api:app", host=host, port=port, reload=reload)


@app.command()
def info() -> None:
    """현재 설정 / 헬스 출력."""
    from .api import healthz
    console.print({"version": __version__, "health": healthz()})


# ──────────────────────── Pipeline subcommands ────────────────────────────

# All stages share a single Container — created lazily inside each command so
# typer --help doesn't trigger PG pool init.

def _container() -> Container:
    return Container(Settings())


@pipeline_app.command("ingest")
def pipeline_ingest():
    """data/*.json → PG (LocalReplaySource → IngestSnapshot)."""
    c = _container()
    n_camps, n_reviews, n_filters = c.ingest_snapshot().execute()
    console.print(f"[ingest] camps={n_camps}  reviews={n_reviews}  filters={n_filters}")
    c.close()


@pipeline_app.command("geocode")
def pipeline_geocode(
    workers: int = typer.Option(1, "--workers", "-w",
                                help="Per-item parallel workers (ignored when the geocoder supports batch — etago fans out internally)."),
    self_heal: bool = typer.Option(
        True, "--self-heal/--no-self-heal",
        help="Default ON: every run NULLs camps.lat/lon for coords shared by ≥3 camps "
             "(admin-region centroids — the '100 camps on one pin' pollution from a "
             "previous Nominatim pass) and drops the matching geocode-cache rows so "
             "they re-resolve cleanly. Once data is clean, this is a no-op.",
    ),
    reset_all: bool = typer.Option(
        False, "--reset-all",
        help="NULL every camps.lat/lon AND clear the entire geocode-cache. Use after "
             "switching providers or to verify a clean re-geocode end-to-end.",
    ),
):
    """address1 → lat/lon via the configured geocoder (cached).

    Switch geocoder via env: ``CAMFIT_GEOCODER=etago`` (default — uses Naver NCP +
    Kakao K1 fallback through the etago binary) or ``CAMFIT_GEOCODER=nominatim``
    (no key needed, lower precision).

    Self-heal is on by default so ``pipeline run-all`` automatically rinses the
    "many camps on one pin" pollution without needing flags. Disable with
    ``--no-self-heal`` if you ever need to debug a specific persisted coord.
    """
    c = _container()
    if reset_all:
        _geocode_reset_all(c)
    elif self_heal:
        _geocode_self_heal(c)
    out = c.geocode_pending().execute(workers=max(1, workers))
    console.print(f"[geocode] provider={c.settings.geocoder} {out}")
    c.close()


def _geocode_reset_all(c: "Container") -> None:
    pool = c._pg
    with pool.conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE camps SET lat=NULL, lon=NULL, geocoded_at=NULL")
        console.print(f"[geocode] reset-all: NULLed {cur.rowcount} camps.lat/lon")
    n = c.geocode_cache.clear()
    console.print(f"[geocode] reset-all: cleared {n} geocode-cache entries")


def _geocode_self_heal(c: "Container") -> None:
    """NULL camps.lat/lon for coords shared by ≥3 camps (admin centroid pollution),
    drop the matching geocode-cache rows so the next pass re-resolves cleanly.
    Idempotent: once data is clean, the dupes CTE returns 0 and this is a no-op.
    """
    pool = c._pg
    with pool.conn() as conn, conn.cursor() as cur:
        cur.execute("""
            WITH dupes AS (
              SELECT lat, lon FROM camps
              WHERE lat IS NOT NULL AND lon IS NOT NULL
              GROUP BY lat, lon HAVING count(*) >= 3
            ),
            nulled AS (
              UPDATE camps c SET lat=NULL, lon=NULL, geocoded_at=NULL
              FROM dupes d
              WHERE c.lat = d.lat AND c.lon = d.lon
              RETURNING c.id
            ),
            purged AS (
              DELETE FROM geocodes g
              USING dupes d
              WHERE g.lat = d.lat AND g.lon = d.lon
              RETURNING g.query
            )
            SELECT (SELECT count(*) FROM nulled),
                   (SELECT count(*) FROM dupes),
                   (SELECT count(*) FROM purged)
        """)
        row = cur.fetchone()
        n_camps, n_clusters, n_cache = row or (0, 0, 0)
    if n_camps:
        console.print(f"[geocode] self-heal: NULLed {n_camps} camps "
                      f"({n_clusters} cluster centers) + dropped {n_cache} stale cache rows")


@pipeline_app.command("vocab")
def pipeline_vocab():
    """Concept seed list + auto-derive from hashtags/facilities → concepts table."""
    c = _container()
    n = c.build_vocabulary().execute()
    console.print(f"[vocab] BuildVocabulary returned n={n}")
    c.close()


@pipeline_app.command("embed")
def pipeline_embed():
    """Run BuildEmbeddings — encode each camp's text into pgvector."""
    c = _container()
    n = c.build_embeddings().execute()
    console.print(f"[embed] {n} camps embedded")
    c.close()


@pipeline_app.command("extract-filter")
def pipeline_extract_filter():
    """ExtractCamfitFilterSignals — collections → camp_filter_signals."""
    c = _container()
    n = c.extract_filter_signals().execute()
    console.print(f"[extract-filter] {n} signals written")
    c.close()


@pipeline_app.command("extract-desc")
def pipeline_extract_desc(
    top_k: int = typer.Option(10),
    min_score: float = typer.Option(0.3),
):
    """ExtractDescSignals — KeyBERT over each camp's embed text."""
    c = _container()
    n = c.extract_desc_signals().execute(top_k=top_k, min_score=min_score)
    console.print(f"[extract-desc] {n} signals written")
    c.close()


@pipeline_app.command("extract-review")
def pipeline_extract_review(
    workers: int = typer.Option(8, "--workers", "-w",
                                help="Parallel workers (≤ PG pool max=8)."),
):
    """ExtractReviewSignals — temperature-weighted negation-aware over each camp's reviews."""
    c = _container()
    total = _extract_review_all(c, workers=workers)
    console.print(f"[extract-review] {total} signals across all camps")
    c.close()


@pipeline_app.command("refresh-agg")
def pipeline_refresh_agg():
    """REFRESH MATERIALIZED VIEW camp_concept_aggregated."""
    c = _container()
    c.refresh_aggregated().execute()
    console.print("[refresh-agg] camp_concept_aggregated refreshed")
    c.close()


@pipeline_app.command("themes")
def pipeline_themes():
    """DiscoverThemes — HDBSCAN over embeddings → themes + camp_themes."""
    c = _container()
    n = c.discover_themes().execute()
    console.print(f"[themes] {n} themes discovered")
    c.close()


@pipeline_app.command("marks")
def pipeline_marks():
    """ComputeMarks — Michelin-style ratings per axis from review temperature."""
    c = _container()
    out = c.compute_marks().execute()
    console.print(f"[marks] {out}")
    c.close()


@pipeline_app.command("discover-synonyms")
def pipeline_discover_synonyms(
    axis: str = typer.Argument(..., help="featured-axis id (e.g. trampoline, halloween, valley)"),
    top_k: int = typer.Option(50, "--top-k", help="max candidates in the report"),
    min_cosine: float = typer.Option(0.55, "--min-cosine", help="cosine threshold for the seed"),
    min_count: int = typer.Option(2, "--min-count", help="discard tokens that appear fewer than N times in the matched subcorpus"),
):
    """DiscoverSynonyms — corpus-driven keyword expansion proposal for a featured axis.

    Mines descriptions+brief+reviews of camps where any current axis keyword
    appears, extracts Korean n-grams, embeds via ko-sroberta, sorts by cosine
    similarity to the seed keyword, and writes data/synonyms_<axis>.md for
    human review. The report is a *recommendation* — paste manually into
    domain/featured_axes.py to register.
    """
    c = _container()
    path = c.discover_synonyms().execute(
        axis, top_k=top_k, min_cosine=min_cosine, min_count=min_count,
    )
    console.print(f"[discover-synonyms] report → {path}")
    c.close()


@pipeline_app.command("rebuild-graph")
def pipeline_rebuild_graph():
    """RebuildGraph — wipe FalkorDB and re-derive from PG."""
    c = _container()
    out = c.rebuild_graph().execute()
    console.print(f"[rebuild-graph] {out}")
    c.close()


@pipeline_app.command("run-all")
def pipeline_run_all(
    workers: int = typer.Option(8, "--workers", "-w",
                                help="Parallel workers for I/O-bound stages "
                                     "(extract-review, geocode). Capped at PG pool max=8."),
):
    """Full pipeline: ingest → geocode → vocab → embed → 3×extract → refresh-agg → themes → marks → rebuild-graph.

    `--workers N` propagates to the parallelizable stages. Stages that don't
    accept a worker count (themes/marks/rebuild-graph/refresh-agg) ignore it.
    """
    geocode_workers = min(workers, 4)  # respect Nominatim 1 rps

    def _run_geocode_stage(c: "Container") -> dict:
        # Self-heal first (idempotent — no-op once data is clean), then
        # resolve any pending coords. Same path as `pipeline geocode`.
        _geocode_self_heal(c)
        return c.geocode_pending().execute(workers=geocode_workers)

    stages = [
        ("ingest",         lambda c: c.ingest_snapshot().execute()),
        ("geocode",        _run_geocode_stage),
        ("vocab",          lambda c: c.build_vocabulary().execute()),
        ("embed",          lambda c: c.build_embeddings().execute()),
        ("extract-filter", lambda c: c.extract_filter_signals().execute(workers=workers)),
        ("extract-desc",   lambda c: c.extract_desc_signals().execute()),
        ("extract-review", lambda c: _extract_review_all(c, workers=workers)),
        ("refresh-agg",    lambda c: (c.refresh_aggregated().execute() or "ok")),
        ("themes",         lambda c: c.discover_themes().execute()),
        ("marks",          lambda c: c.compute_marks().execute()),
        ("rebuild-graph",  lambda c: c.rebuild_graph().execute()),
    ]
    c = _container()
    try:
        for name, fn in stages:
            console.print(f"[pipeline] {name} ...")
            r = fn(c)
            console.print(f"           → {r}")
    finally:
        c.close()


def _extract_review_all(c: Container, *, workers: int = 8) -> int:
    """Run ExtractReviewSignals across every camp.

    Each camp_id is processed in its own thread; the use-case grabs a fresh PG
    connection from the pool per call (writers/readers acquire on every method).
    `iter_all()` yields each camp_id exactly once, so reset_for + upsert is
    race-free across workers.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    workers = max(1, min(workers, 8))
    uc = c.extract_review_signals()
    camp_ids = [camp.id for camp in c.camps_read.iter_all()]
    if not camp_ids:
        return 0
    if workers == 1:
        return sum(uc.execute(cid) for cid in camp_ids)
    total = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(uc.execute, cid) for cid in camp_ids]
        for f in as_completed(futs):
            total += f.result()
    return total


if __name__ == "__main__":
    app()
