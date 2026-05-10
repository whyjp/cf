from __future__ import annotations
from .pool import PostgresPool


class PostgresFilterConceptMappingRepo:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def upsert_mapping(self, filter_id: str, concept_id: str, polarity: int) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                """INSERT INTO filter_concept_mapping (filter_id, concept_id, polarity)
                   VALUES (%s,%s,%s)
                   ON CONFLICT (filter_id, concept_id) DO UPDATE SET polarity=EXCLUDED.polarity""",
                (filter_id, concept_id, polarity),
            )

    def for_filter(self, filter_id: str) -> list[tuple[str, int]]:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                "SELECT concept_id, polarity FROM filter_concept_mapping WHERE filter_id=%s",
                (filter_id,),
            )
            return cur.fetchall()
