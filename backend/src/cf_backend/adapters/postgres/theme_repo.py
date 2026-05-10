from __future__ import annotations
from typing import Optional
from ...domain.models import Theme
from .pool import PostgresPool


class PostgresThemeRepo:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def replace_all(self, themes: list[Theme]) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("DELETE FROM camp_themes")
            cur.execute("DELETE FROM themes")
            for t in themes:
                cur.execute(
                    """INSERT INTO themes (id, label, centroid, member_count, manual_label)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (t.id, t.label, t.centroid, t.member_count, t.manual_label),
                )

    def assign(self, camp_id: str, theme_id: str) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                """INSERT INTO camp_themes (camp_id, theme_id) VALUES (%s,%s)
                   ON CONFLICT (camp_id) DO UPDATE SET theme_id=EXCLUDED.theme_id""",
                (camp_id, theme_id),
            )

    def for_camp(self, camp_id: str) -> Optional[Theme]:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                """SELECT t.id, t.label, t.member_count, t.manual_label
                   FROM themes t JOIN camp_themes ct ON t.id=ct.theme_id
                   WHERE ct.camp_id=%s""",
                (camp_id,),
            )
            r = cur.fetchone()
            return Theme(id=r[0], label=r[1], member_count=r[2], manual_label=r[3]) if r else None

    def all(self) -> list[Theme]:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                "SELECT id, label, member_count, manual_label FROM themes ORDER BY member_count DESC"
            )
            return [
                Theme(id=r[0], label=r[1], member_count=r[2], manual_label=r[3])
                for r in cur.fetchall()
            ]
