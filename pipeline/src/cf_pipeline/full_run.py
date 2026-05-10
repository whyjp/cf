"""full_run -- orchestrate 5 pipeline stages.

Stage order (each idempotent):
  1. ingest_camps    : crawl/{camfit,txcp}/data/*.jsonl → postgres camps upsert
  2. geocode_run     : null lat/lon rows → etago binary → UPDATE
  3. rebuild_graph   : postgres → falkor
  4. derive_lexicon  : keyword/synonym dict refresh
  5. seed_concepts + seed_filter_mapping : theme + filter mapping
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from loguru import logger

app = typer.Typer(no_args_is_help=False, add_completion=False)

STAGES = [
    "ingest_camps",
    "geocode_run",
    "rebuild_graph",
    "derive_lexicon",
    "seed_concepts",
    "seed_filter_mapping",
]


@app.command()
def main(
    camfit_data: Path = typer.Option(Path("crawl/camfit/data"), help="camfit data dir"),
    txcp_data: Path = typer.Option(Path("crawl/txcp/data"), help="txcp data dir"),
    only: Optional[str] = typer.Option(None, help="run only this stage"),
    skip: list[str] = typer.Option([], help="skip these stages"),
    dry_run: bool = typer.Option(False, help="print plan without executing"),
) -> None:
    selected = [s for s in STAGES if (only is None or s == only) and s not in skip]
    if not selected:
        typer.echo("No stages selected. Available: " + ", ".join(STAGES), err=True)
        raise typer.Exit(code=1)

    typer.echo("=== cf-pipeline full_run plan ===")
    typer.echo(f"camfit_data = {camfit_data}")
    typer.echo(f"txcp_data   = {txcp_data}")
    typer.echo(f"dry_run     = {dry_run}")
    typer.echo(f"stages      = {selected}")
    if only is None and skip:
        typer.echo(f"skipped     = {skip}")

    for stage in STAGES:
        if stage in selected:
            typer.echo(f"  RUN  {stage}")
        else:
            typer.echo(f"  skip {stage}")

    if dry_run:
        typer.echo("=== DRY RUN -- no execution ===")
        raise typer.Exit(code=0)

    # Real execution: each stage is currently a __main__-style script ported from
    # camfit-puller. Until each stage exposes a clean def run(...) adapter, the
    # orchestrator dispatches best-effort. Stretch: convert each ported script
    # into def run(...) for in-process call.
    for stage in selected:
        logger.info(f"--- stage: {stage} ---")
        if stage == "ingest_camps":
            from cf_pipeline import ingest_camps
            _try_run_module(ingest_camps)
        elif stage == "geocode_run":
            from cf_pipeline import geocode_run
            _try_run_module(geocode_run)
        elif stage == "rebuild_graph":
            from cf_pipeline import load_rich
            _try_run_module(load_rich)
        elif stage == "derive_lexicon":
            from cf_pipeline import derive_lexicon
            _try_run_module(derive_lexicon)
        elif stage == "seed_concepts":
            from cf_pipeline import seed_concepts
            _try_run_module(seed_concepts)
        elif stage == "seed_filter_mapping":
            from cf_pipeline import seed_filter_mapping
            _try_run_module(seed_filter_mapping)


def _try_run_module(module):
    """Best-effort dispatch -- calls module.run() if defined; else
    falls back to module.main() or notes that the stage needs an adapter."""
    if hasattr(module, "run") and callable(module.run):
        return module.run()
    if hasattr(module, "main") and callable(module.main):
        return module.main()
    logger.warning(
        f"stage module {module.__name__} lacks run()/main() adapter -- "
        f"original __main__-only script. Port to def run(...) for in-process exec."
    )


if __name__ == "__main__":
    app()
