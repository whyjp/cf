"""Postgres adapter for MarkRepository."""
from __future__ import annotations

from ...domain.models import Mark
from .pool import PostgresPool


_LEVELS_ORDER = ["bib", "recommended", "notable", "exceptional"]


class PostgresMarkRepo:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def replace_for_camp(self, camp_id: str, marks: list[Mark]) -> int:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM camp_marks WHERE camp_id=%s", (camp_id,))
            n = 0
            for m in marks:
                cur.execute(
                    """INSERT INTO camp_marks (camp_id, axis, level, score, evidence)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (m.camp_id, m.axis, m.level, m.score, m.evidence),
                )
                n += 1
        return n

    def for_camp(self, camp_id: str) -> list[Mark]:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute(
                """SELECT camp_id, axis, level, score, evidence
                   FROM camp_marks WHERE camp_id=%s
                   ORDER BY axis""",
                (camp_id,),
            )
            return [
                Mark(
                    camp_id=r[0], axis=r[1], level=r[2],
                    score=float(r[3]), evidence=r[4],
                )
                for r in cur.fetchall()
            ]

    def for_axis(self, axis: str, *, min_level: str | None = None,
                 limit: int = 100) -> list[Mark]:
        with self._pool.conn() as c, c.cursor() as cur:
            if min_level:
                if min_level not in _LEVELS_ORDER:
                    raise ValueError(f"invalid level: {min_level}")
                allowed = _LEVELS_ORDER[_LEVELS_ORDER.index(min_level):]
                placeholders = ",".join(["%s"] * len(allowed))
                cur.execute(
                    f"""SELECT camp_id, axis, level, score, evidence
                       FROM camp_marks
                       WHERE axis=%s AND level IN ({placeholders})
                       ORDER BY score DESC LIMIT %s""",
                    (axis, *allowed, limit),
                )
            else:
                cur.execute(
                    """SELECT camp_id, axis, level, score, evidence
                       FROM camp_marks WHERE axis=%s
                       ORDER BY score DESC LIMIT %s""",
                    (axis, limit),
                )
            return [
                Mark(camp_id=r[0], axis=r[1], level=r[2],
                     score=float(r[3]), evidence=r[4])
                for r in cur.fetchall()
            ]

    def all_axes(self) -> list[tuple[str, int]]:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute(
                "SELECT axis, count(*) FROM camp_marks GROUP BY axis ORDER BY count(*) DESC"
            )
            return cur.fetchall()
