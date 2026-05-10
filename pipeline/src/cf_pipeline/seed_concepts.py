"""Seed the `concepts` table with the curated SEEDS list + auto-derived
hashtags/facilities from the loaded camp corpus (BuildVocabulary use-case).

Run order:
    1. After migrate_to_pg.py loaded camps with their hashtags/facilities.
    2. Before any extract-* signal use-case (those depend on concepts).

Idempotent: re-running upserts seeds and adds any new hashtag/facility-derived
concepts.
"""
from __future__ import annotations
import sys

from cf_backend.settings import Settings
from cf_backend.container import Container
from rich.console import Console


def main() -> int:
    console = Console()
    s = Settings(embedder="mock")  # mock: BuildVocabulary doesn't need embeddings
    c = Container(s)

    pre = len(c.concept_repo.all())
    n = c.build_vocabulary().execute()
    post = len(c.concept_repo.all())

    console.print(f"[seed_concepts] BuildVocabulary returned n={n}")
    console.print(f"[seed_concepts] concepts in PG: pre={pre}  post={post}  net+={post - pre}")

    # Quick category breakdown
    by_cat: dict[str, int] = {}
    for concept in c.concept_repo.all():
        by_cat[concept.category or "(none)"] = by_cat.get(concept.category or "(none)", 0) + 1
    console.print(f"[seed_concepts] by category:")
    for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
        console.print(f"   {cat:20s}  {count}")

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
