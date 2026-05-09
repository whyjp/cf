from __future__ import annotations
from ...domain.models import Concept, CampConcept
from .pool import PostgresPool


class PostgresConceptRepo:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def upsert_concept(self, c: Concept) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                """INSERT INTO concepts (id, name, source, category, description, is_axis)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                     name=EXCLUDED.name, source=EXCLUDED.source, category=EXCLUDED.category,
                     description=EXCLUDED.description, is_axis=EXCLUDED.is_axis""",
                (c.id, c.name, c.source, c.category, c.description, c.is_axis),
            )

    def assign(self, camp_id: str, concept_id: str, score: float, evidence: str | None = None) -> None:
        # Default writer = camp_filter_signals (camfit native filter source).
        # Other signal writers in signal_repos.py are dedicated.
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                """INSERT INTO camp_filter_signals (camp_id, concept_id, score, evidence)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (camp_id, concept_id) DO UPDATE SET
                     score=EXCLUDED.score, evidence=EXCLUDED.evidence""",
                (camp_id, concept_id, score, evidence),
            )

    def for_camp(self, camp_id: str) -> list[CampConcept]:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                "SELECT camp_id, concept_id, final_score FROM camp_concept_aggregated WHERE camp_id=%s",
                (camp_id,),
            )
            return [CampConcept(camp_id=r[0], concept_id=r[1], score=float(r[2])) for r in cur.fetchall()]

    def all(self) -> list[Concept]:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                "SELECT id, name, source, category, description, is_axis FROM concepts"
            )
            return [
                Concept(
                    id=r[0], name=r[1], source=r[2], category=r[3],
                    description=r[4], is_axis=r[5],
                )
                for r in cur.fetchall()
            ]

    def find_by_name(self, name: str):
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                "SELECT id, name, source, category, description, is_axis FROM concepts WHERE name=%s",
                (name,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return Concept(
                id=row[0], name=row[1], source=row[2], category=row[3],
                description=row[4], is_axis=row[5],
            )

    def delete_by_id(self, concept_id: str) -> None:
        # FK constraints on signal tables use ON DELETE CASCADE — see
        # alembic 0001_initial.py — so dependent rows clean up transparently.
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("DELETE FROM concepts WHERE id=%s", (concept_id,))
