from __future__ import annotations
from contextlib import contextmanager
import psycopg
from psycopg_pool import ConnectionPool


class PostgresPool:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 8):
        self._pool = ConnectionPool(dsn, min_size=min_size, max_size=max_size, open=True)

    @contextmanager
    def conn(self):
        with self._pool.connection() as c:
            yield c

    def close(self) -> None:
        self._pool.close()
