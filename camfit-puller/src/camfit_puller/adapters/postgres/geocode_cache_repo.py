from __future__ import annotations
import json
from typing import Optional
from .pool import PostgresPool


class PostgresGeocodeCacheRepo:
    """Cache layer for address → (lat, lon) geocode lookups.

    Stored in `geocodes` table. Address text is the cache key (PK).
    """

    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def get(self, query: str) -> Optional[tuple[float, float]]:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("SELECT lat, lon FROM geocodes WHERE query=%s", (query,))
            r = cur.fetchone()
            if r and r[0] is not None and r[1] is not None:
                return (float(r[0]), float(r[1]))
            return None

    def put(self, query: str, lat: Optional[float], lon: Optional[float],
            source: str, raw: dict | None = None) -> None:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute(
                """INSERT INTO geocodes (query, lat, lon, source, raw)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (query) DO UPDATE SET
                     lat=EXCLUDED.lat, lon=EXCLUDED.lon, source=EXCLUDED.source,
                     raw=EXCLUDED.raw, cached_at=now()""",
                (query, lat, lon, source, json.dumps(raw) if raw else None),
            )

    def clear(self) -> int:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM geocodes")
            return cur.rowcount
