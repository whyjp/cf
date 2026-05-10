from __future__ import annotations
import json
from .pool import PostgresPool


class PostgresCamfitFilterRepo:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def upsert(self, filter_id: str, name: str, kind: str, raw: dict | None) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute(
                """INSERT INTO camfit_filters (id, name, kind, raw)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                     name=EXCLUDED.name, kind=EXCLUDED.kind, raw=EXCLUDED.raw""",
                (filter_id, name, kind, json.dumps(raw) if raw else None),
            )

    def all(self) -> list[tuple[str, str, str]]:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("SELECT id, name, kind FROM camfit_filters")
            return cur.fetchall()
