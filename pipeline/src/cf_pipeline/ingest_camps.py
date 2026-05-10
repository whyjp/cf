"""Source-aware ingest: jsonl/json -> PostgreSQL.

Idempotent. Re-run any time. Picks DataSource by --source flag:
  --source camfit  : LocalReplaySource over crawl/camfit/data (camps_dedup.json)
  --source txcp    : TxcpJsonlSource over crawl/txcp/data (camps.jsonl)
  --source both    : run both sequentially (default)

Each DataSource yields DomainCamp with the proper source / detail_url set;
the shared IngestSnapshot usecase + PostgresCampWriter dest path is identical.

Usage:
    python -m cf_pipeline.ingest_camps                           # both
    python -m cf_pipeline.ingest_camps --source camfit
    python -m cf_pipeline.ingest_camps --source txcp --dry-run
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from rich.console import Console

from cf_be_api.adapters.source.local_replay import LocalReplaySource
from cf_be_api.adapters.source.txcp_jsonl import TxcpJsonlSource
from cf_be_api.container import Container
from cf_be_api.settings import Settings
from cf_be_api.usecases.ingest_snapshot import IngestSnapshot

Source = Literal["camfit", "txcp", "both"]

# magic-number-traceability: data dirs default to repo-relative locations.
# crawl-camfit and crawl-txcp packages emit into these dirs.
_DEFAULT_CAMFIT_DATA = Path("crawl/camfit/data")
_DEFAULT_TXCP_DATA = Path("crawl/txcp/data")


def _ingest_camfit(c: Container, data_dir: Path, dry_run: bool, console: Console) -> tuple[int, int, int]:
    src = LocalReplaySource(data_dir)
    summaries = list(src.iter_summaries())
    console.print(f"[camfit] summaries: {len(summaries)} (data_dir={data_dir})")
    if dry_run:
        if summaries:
            first = summaries[0]
            detail = src.get_detail(first.id)
            reviews = list(src.iter_reviews(first.id))
            console.print(
                f"[camfit dry-run] {first.id} -> detail={'ok' if detail else 'missing'} "
                f"reviews={len(reviews)} detail_url={first.detail_url}"
            )
        return (0, 0, 0)
    uc = IngestSnapshot(
        source=src,
        camp_writer=c.camps_write,
        review_writer=c.reviews_write,
        filter_repo=c.filter_repo,
    )
    return uc.execute()


def _ingest_txcp(c: Container, data_dir: Path, dry_run: bool, console: Console) -> tuple[int, int, int]:
    src = TxcpJsonlSource(data_dir)
    summaries = list(src.iter_summaries())
    console.print(f"[txcp] summaries: {len(summaries)} (data_dir={data_dir})")
    if dry_run:
        if summaries:
            first = summaries[0]
            console.print(
                f"[txcp dry-run] {first.id} -> source={first.source} "
                f"detail_url={first.detail_url}"
            )
        return (0, 0, 0)
    uc = IngestSnapshot(
        source=src,
        camp_writer=c.camps_write,
        review_writer=c.reviews_write,
        filter_repo=c.filter_repo,
    )
    return uc.execute()


def run(
    source: Source = "both",
    *,
    camfit_data: Path = _DEFAULT_CAMFIT_DATA,
    txcp_data: Path = _DEFAULT_TXCP_DATA,
    dry_run: bool = False,
) -> dict:
    """In-process entry: dispatch by source flag, return per-source counts."""
    console = Console()
    s = Settings(data_source="local-replay", embedder="mock")
    c = Container(s)
    out: dict = {}
    try:
        if source in ("camfit", "both"):
            n_camps, n_reviews, n_filters = _ingest_camfit(c, camfit_data, dry_run, console)
            out["camfit"] = {"camps": n_camps, "reviews": n_reviews, "filters": n_filters}
        if source in ("txcp", "both"):
            n_camps, n_reviews, n_filters = _ingest_txcp(c, txcp_data, dry_run, console)
            out["txcp"] = {"camps": n_camps, "reviews": n_reviews, "filters": n_filters}
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
    args = parser.parse_args()
    run(
        source=args.source,
        camfit_data=args.camfit_data,
        txcp_data=args.txcp_data,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
