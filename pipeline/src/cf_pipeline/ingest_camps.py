"""Source-aware ingest: jsonl/json -> PostgreSQL.

Idempotent. Re-run any time. Picks DataSource by --source flag:
  --source camfit  : LocalReplaySource over crawl/camfit/data (camps_dedup.json)
  --source txcp    : TxcpJsonlSource over crawl/txcp/data (camps.jsonl)
  --source both    : run both sequentially (default)

Each DataSource yields DomainCamp with the proper source / detail_url set;
the shared IngestSnapshot usecase + PostgresCampWriter dest path is identical.

Modes:
  full (default)           : every yielded summary is upserted (ON CONFLICT DO UPDATE).
  --incremental            : skip ids already present in PG (existing_ids_by_source).
                              new_ids list returned/printed for downstream chaining.

Usage:
    python -m cf_pipeline.ingest_camps                                  # full both
    python -m cf_pipeline.ingest_camps --source camfit                  # full camfit
    python -m cf_pipeline.ingest_camps --source txcp --incremental      # only new txcp
    python -m cf_pipeline.ingest_camps --source txcp --dry-run          # report counts only
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from rich.console import Console

from cf_be_api.adapters.source.local_replay import LocalReplaySource
from cf_be_api.adapters.source.txcp_jsonl import TxcpJsonlSource
from cf_be_api.container import Container
from cf_be_api.settings import Settings

Source = Literal["camfit", "txcp", "both"]

# magic-number-traceability: data dirs default to repo-relative locations.
# crawl-camfit and crawl-txcp packages emit into these dirs.
_DEFAULT_CAMFIT_DATA = Path("crawl/camfit/data")
_DEFAULT_TXCP_DATA = Path("crawl/txcp/data")


def _source_name(src) -> str:
    """Map DataSource instance to its persisted 'source' string."""
    if isinstance(src, LocalReplaySource):
        return "camfit"
    if isinstance(src, TxcpJsonlSource):
        return "txcp"
    return getattr(src, "name", "unknown")


def _ingest_with_source(
    c: Container,
    src,
    label: str,
    data_dir: Path,
    dry_run: bool,
    incremental: bool,
    console: Console,
) -> tuple[int, int, int, list[str]]:
    """Ingest summaries+details+reviews from src.

    Returns (camps_n, reviews_n, filters_n, new_ids).
    incremental=True: filter to ids not already present (existing_ids_by_source).
    """
    source_str = _source_name(src)
    summaries_full = list(src.iter_summaries())
    if incremental:
        existing = c.camps_read.existing_ids_by_source(source_str)
        summaries = [s for s in summaries_full if s.id not in existing]
    else:
        summaries = summaries_full

    console.print(
        f"[{label}] summaries: full={len(summaries_full)} new={len(summaries)} "
        f"(data_dir={data_dir} incremental={incremental})"
    )

    if dry_run:
        if summaries:
            first = summaries[0]
            console.print(
                f"[{label} dry-run] first new {first.id} -> source={first.source} detail_url={first.detail_url}"
            )
        return (0, 0, 0, [s.id for s in summaries])

    if not summaries:
        return (0, 0, 0, [])

    new_ids = [s.id for s in summaries]

    # Upsert with detail-merged Camp where source supports it
    enriched = [(src.get_detail(s.id) or s) for s in summaries]
    c.camps_write.upsert_many(enriched)

    # Reviews per camp (where supported)
    n_reviews = 0
    for cid in new_ids:
        batch = list(src.iter_reviews(cid))
        if batch:
            c.reviews_write.upsert_many(batch)
            n_reviews += len(batch)

    # Filters: global per source. Only re-seed on full ingest (incremental skips).
    n_filters = 0
    if not incremental:
        for fid, name, kind, raw in src.iter_filters():
            c.filter_repo.upsert(fid, name, kind, raw)
            n_filters += 1

    return len(summaries), n_reviews, n_filters, new_ids


def _ingest_camfit(c: Container, data_dir: Path, dry_run: bool, incremental: bool, console: Console):
    src = LocalReplaySource(data_dir)
    return _ingest_with_source(c, src, "camfit", data_dir, dry_run, incremental, console)


def _ingest_txcp(c: Container, data_dir: Path, dry_run: bool, incremental: bool, console: Console):
    src = TxcpJsonlSource(data_dir)
    return _ingest_with_source(c, src, "txcp", data_dir, dry_run, incremental, console)


def run(
    source: Source = "both",
    *,
    camfit_data: Path = _DEFAULT_CAMFIT_DATA,
    txcp_data: Path = _DEFAULT_TXCP_DATA,
    dry_run: bool = False,
    incremental: bool = False,
) -> dict:
    """In-process entry: dispatch by source flag, return per-source counts + new_ids.

    incremental=True: skip ids already present in PG. Returned new_ids per source
    is the list of newly-upserted ids — pipe directly into rebuild_graph(--ids)
    for partial graph update.
    """
    console = Console()
    s = Settings(data_source="local-replay", embedder="mock")
    c = Container(s)
    out: dict = {}
    try:
        if source in ("camfit", "both"):
            n_camps, n_reviews, n_filters, new_ids = _ingest_camfit(c, camfit_data, dry_run, incremental, console)
            out["camfit"] = {"camps": n_camps, "reviews": n_reviews, "filters": n_filters, "new_ids": new_ids}
        if source in ("txcp", "both"):
            n_camps, n_reviews, n_filters, new_ids = _ingest_txcp(c, txcp_data, dry_run, incremental, console)
            out["txcp"] = {"camps": n_camps, "reviews": n_reviews, "filters": n_filters, "new_ids": new_ids}
        if not dry_run:
            console.print(f"[done] PG camps.count() = {c.camps_read.count()}")
    finally:
        c.close()
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["camfit", "txcp", "both"], default="both")
    parser.add_argument("--camfit-data", type=Path, default=_DEFAULT_CAMFIT_DATA)
    parser.add_argument("--txcp-data", type=Path, default=_DEFAULT_TXCP_DATA)
    parser.add_argument("--dry-run", action="store_true", help="Don't write to PG; just report counts.")
    parser.add_argument("--incremental", action="store_true",
                        help="Skip ids already in PG (only upsert new). Output new_ids list.")
    args = parser.parse_args()
    out = run(
        source=args.source,
        camfit_data=args.camfit_data,
        txcp_data=args.txcp_data,
        dry_run=args.dry_run,
        incremental=args.incremental,
    )
    new_ids_summary = {k: v.get("new_ids", []) for k, v in out.items()}
    print(json.dumps({"new_ids": new_ids_summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
