from __future__ import annotations
from typing import Iterable, Optional
import numpy as np
from ..postgres.pool import PostgresPool


class PgvectorIndex:
    """Implements ports.vector.VectorIndex against pgvector in PostgreSQL.

    Items are stored in `camp_embeddings` (camp_id PK, vec vector(768),
    text_hash, model_name, created_at). KNN uses HNSW index `idx_camp_embeddings_hnsw`
    with cosine distance.
    """

    def __init__(self, pool: PostgresPool, *, dim: int = 768, model_name: str = "ko-sroberta"):
        self._pool = pool
        self._dim = dim
        self._model = model_name

    @property
    def dim(self) -> int:
        return self._dim

    def upsert_many(self, items: Iterable[tuple[str, np.ndarray, str]]) -> int:
        from pgvector.psycopg import register_vector
        n = 0
        with self._pool.conn() as c:
            register_vector(c)
            with c.cursor() as cur:
                for cid, vec, text_h in items:
                    cur.execute(
                        """INSERT INTO camp_embeddings (camp_id, vec, text_hash, model_name)
                           VALUES (%s, %s, %s, %s)
                           ON CONFLICT (camp_id) DO UPDATE SET
                             vec=EXCLUDED.vec, text_hash=EXCLUDED.text_hash,
                             model_name=EXCLUDED.model_name, created_at=now()""",
                        (cid, vec, text_h, self._model),
                    )
                    n += 1
        return n

    def knn(self, query: np.ndarray, k: int = 10,
            filter_ids: set[str] | None = None) -> list[tuple[str, float]]:
        from pgvector.psycopg import register_vector
        with self._pool.conn() as c:
            register_vector(c)
            with c.cursor() as cur:
                if filter_ids:
                    cur.execute(
                        """SELECT camp_id, 1 - (vec <=> %s) AS sim FROM camp_embeddings
                           WHERE camp_id = ANY(%s) ORDER BY vec <=> %s LIMIT %s""",
                        (query, list(filter_ids), query, k),
                    )
                else:
                    cur.execute(
                        """SELECT camp_id, 1 - (vec <=> %s) AS sim FROM camp_embeddings
                           ORDER BY vec <=> %s LIMIT %s""",
                        (query, query, k),
                    )
                return [(r[0], float(r[1])) for r in cur.fetchall()]

    def get(self, item_id: str) -> Optional[np.ndarray]:
        from pgvector.psycopg import register_vector
        with self._pool.conn() as c:
            register_vector(c)
            with c.cursor() as cur:
                cur.execute("SELECT vec FROM camp_embeddings WHERE camp_id=%s", (item_id,))
                row = cur.fetchone()
                return np.array(row[0]) if row else None

    def size(self) -> int:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM camp_embeddings")
            return cur.fetchone()[0]

    def reset(self) -> None:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM camp_embeddings")
