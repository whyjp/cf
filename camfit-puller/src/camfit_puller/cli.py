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
def pipeline_geocode():
    """address1 → lat/lon via Nominatim (cached)."""
    c = _container()
    out = c.geocode_pending().execute()
    console.print(f"[geocode] {out}")
    c.close()


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
def pipeline_extract_review():
    """ExtractReviewSignals — temperature-weighted negation-aware over each camp's reviews."""
    c = _container()
    uc = c.extract_review_signals()
    total = 0
    for camp in c.camps_read.iter_all():
        n = uc.execute(camp.id)
        total += n
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


@pipeline_app.command("rebuild-graph")
def pipeline_rebuild_graph():
    """RebuildGraph — wipe FalkorDB and re-derive from PG."""
    c = _container()
    out = c.rebuild_graph().execute()
    console.print(f"[rebuild-graph] {out}")
    c.close()


@pipeline_app.command("run-all")
def pipeline_run_all():
    """Full pipeline in order: ingest → geocode → vocab → embed → 3×extract → refresh-agg → themes → rebuild-graph."""
    stages = [
        ("ingest",         lambda c: c.ingest_snapshot().execute()),
        ("geocode",        lambda c: c.geocode_pending().execute()),
        ("vocab",          lambda c: c.build_vocabulary().execute()),
        ("embed",          lambda c: c.build_embeddings().execute()),
        ("extract-filter", lambda c: c.extract_filter_signals().execute()),
        ("extract-desc",   lambda c: c.extract_desc_signals().execute()),
        ("extract-review", lambda c: _extract_review_all(c)),
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


def _extract_review_all(c: Container) -> int:
    uc = c.extract_review_signals()
    total = 0
    for camp in c.camps_read.iter_all():
        total += uc.execute(camp.id)
    return total


if __name__ == "__main__":
    app()
