"""NumPy in-memory VectorIndex — implements ports.vector.VectorIndex.

Useful for:
- Unit tests that don't need PG.
- Local development without docker.
- OCP verification (contract test parity with PgvectorIndex).

Persistence: NONE. Reset on process restart.
"""
from __future__ import annotations
from typing import Iterable, Optional

import numpy as np


class NumpyVectorIndex:
    def __init__(self, *, dim: int = 768, model_name: str = "mock"):
        self._dim = dim
        self._model = model_name
        self._items: dict[str, np.ndarray] = {}
        self._hashes: dict[str, str] = {}

    @property
    def dim(self) -> int:
        return self._dim

    def upsert_many(self, items: Iterable[tuple[str, np.ndarray, str]]) -> int:
        n = 0
        for cid, vec, text_h in items:
            v = np.asarray(vec, dtype=np.float32)
            if v.shape != (self._dim,):
                raise ValueError(f"vector shape {v.shape} != ({self._dim},)")
            self._items[cid] = v
            self._hashes[cid] = text_h
            n += 1
        return n

    def knn(self, query: np.ndarray, k: int = 10,
            filter_ids: set[str] | None = None) -> list[tuple[str, float]]:
        if not self._items:
            return []
        q = np.asarray(query, dtype=np.float32)
        candidates = self._items.items() if not filter_ids else (
            (cid, v) for cid, v in self._items.items() if cid in filter_ids
        )
        # Cosine similarity (assumes inputs are L2-normalized but compute defensively)
        results = []
        q_norm = np.linalg.norm(q) + 1e-9
        for cid, v in candidates:
            v_norm = np.linalg.norm(v) + 1e-9
            sim = float(np.dot(v, q) / (v_norm * q_norm))
            results.append((cid, sim))
        results.sort(key=lambda x: -x[1])
        return results[:k]

    def get(self, item_id: str) -> Optional[np.ndarray]:
        return self._items.get(item_id)

    def size(self) -> int:
        return len(self._items)

    def reset(self) -> None:
        self._items.clear()
        self._hashes.clear()
