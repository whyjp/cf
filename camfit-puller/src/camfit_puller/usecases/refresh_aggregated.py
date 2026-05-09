"""Use-case: refresh `camp_concept_aggregated` materialized view.

Postgres-specific (REFRESH MATERIALIZED VIEW). The view aggregates the three
signal sources (filter / review / description) with weights 1.0 / 0.7 / 0.5 into
a single `final_score` per (camp_id, concept_id).

This must be called after any signal table mutation (filter/desc/review) to make
fresh values visible to the API's filter queries.
"""
from __future__ import annotations
from dataclasses import dataclass

from ..adapters.postgres.pool import PostgresPool


@dataclass
class RefreshAggregatedSignals:
    """Note: depends on concrete PostgresPool — `REFRESH MATERIALIZED VIEW` is a
    Postgres-specific operation, not part of the abstract GraphStore/repo ports.
    Acceptable per spec (each adapter exposes its idiomatic operations)."""

    pool: PostgresPool

    def execute(self) -> None:
        with self.pool.conn() as c, c.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW camp_concept_aggregated")
