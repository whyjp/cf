from __future__ import annotations
from .pool import PostgresPool


class PostgresFilterSignalWriter:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def upsert(self, camp_id: str, concept_id: str, score: float, evidence: str | None) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                """INSERT INTO camp_filter_signals (camp_id, concept_id, score, evidence)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (camp_id, concept_id) DO UPDATE SET
                     score=EXCLUDED.score, evidence=EXCLUDED.evidence""",
                (camp_id, concept_id, score, evidence),
            )

    def reset_for(self, camp_id: str) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("DELETE FROM camp_filter_signals WHERE camp_id=%s", (camp_id,))


class PostgresDescSignalWriter:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def upsert(self, camp_id: str, concept_id: str, score: float) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                """INSERT INTO camp_desc_signals (camp_id, concept_id, score)
                   VALUES (%s,%s,%s)
                   ON CONFLICT (camp_id, concept_id) DO UPDATE SET score=EXCLUDED.score""",
                (camp_id, concept_id, score),
            )

    def reset_for(self, camp_id: str) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("DELETE FROM camp_desc_signals WHERE camp_id=%s", (camp_id,))


class PostgresReviewSignalWriter:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def upsert(self, camp_id: str, concept_id: str, score: float,
               pos_count: int, neg_count: int, evidence: str | None) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                """INSERT INTO camp_review_signals (camp_id, concept_id, score, pos_count, neg_count, evidence)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (camp_id, concept_id) DO UPDATE SET
                     score=EXCLUDED.score, pos_count=EXCLUDED.pos_count,
                     neg_count=EXCLUDED.neg_count, evidence=EXCLUDED.evidence""",
                (camp_id, concept_id, score, pos_count, neg_count, evidence),
            )

    def reset_for(self, camp_id: str) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("DELETE FROM camp_review_signals WHERE camp_id=%s", (camp_id,))
