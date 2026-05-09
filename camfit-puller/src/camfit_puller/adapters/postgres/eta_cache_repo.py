from __future__ import annotations
from typing import Optional
from .pool import PostgresPool


class PostgresEtaCacheRepo:
    """Cache layer for (origin, dest) → minutes ETA lookups.

    Stored in `eta_cache` table. (origin, dest) is the composite key.
    """

    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def get(self, origin: str, dest: str) -> Optional[tuple[int, str]]:
        """Returns (minutes, source) or None."""
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute(
                "SELECT minutes, source FROM eta_cache WHERE origin=%s AND dest=%s",
                (origin, dest),
            )
            r = cur.fetchone()
            if r and r[0] is not None:
                return (int(r[0]), r[1] or "")
            return None

    def put(self, origin: str, dest: str, minutes: Optional[int], source: str) -> None:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute(
                """INSERT INTO eta_cache (origin, dest, minutes, source)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (origin, dest) DO UPDATE SET
                     minutes=EXCLUDED.minutes, source=EXCLUDED.source, cached_at=now()""",
                (origin, dest, minutes, source),
            )

    def clear(self) -> int:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM eta_cache")
            return cur.rowcount
