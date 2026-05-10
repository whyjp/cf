"""One-shot ETL: data/*.json (CloakBrowser-fetched) → PostgreSQL.

Idempotent. Re-run any time. Pulls fresh files added by background P1 fetch.

Usage:
    cd D:/github/cf/camfit-puller
    python scripts/migrate_to_pg.py             # full migration
    python scripts/migrate_to_pg.py --dry-run    # no writes; just count
"""
from __future__ import annotations
import argparse
import sys

from cf_be_api.settings import Settings
from cf_be_api.container import Container
from rich.console import Console


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Don't write to PG; just report counts.")
    args = parser.parse_args()

    console = Console()

    # Force LocalReplaySource as the data source (the only one for offline ETL)
    s = Settings(data_source="local-replay", embedder="mock")  # mock embedder = no model load
    c = Container(s)

    console.print(f"[migrate] data_dir={s.data_dir}")

    # Pre-flight: count files
    summaries = list(c.source.iter_summaries())
    console.print(f"[migrate] summaries from local-replay: {len(summaries)}")

    if args.dry_run:
        # Sample first detail + reviews
        if summaries:
            first = summaries[0]
            detail = c.source.get_detail(first.id)
            reviews = list(c.source.iter_reviews(first.id))
            console.print(f"[dry-run] sample: {first.id} → detail={'ok' if detail else 'missing'} "
                          f"reviews={len(reviews)}")
        c.close()
        return 0

    # Run ingest
    uc = c.ingest_snapshot()
    console.print("[migrate] ingest_snapshot starting ...")
    n_camps, n_reviews, n_filters = uc.execute()
    console.print(f"[migrate] DONE  camps={n_camps}  reviews={n_reviews}  filters={n_filters}")

    # Quick post-conditions via PG repos
    pg_camp_count = c.camps_read.count()
    console.print(f"[migrate] PG camps.count() = {pg_camp_count}")

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
