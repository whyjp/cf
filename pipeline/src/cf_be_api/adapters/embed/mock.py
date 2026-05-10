"""Deterministic, zero-dependency embedder for unit tests. dim 768 matches ko-sroberta."""
from __future__ import annotations
import hashlib
import numpy as np


class MockEmbedder:
    model_name = "mock"

    def __init__(self, dim: int = 768):
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def encode_one(self, text: str) -> np.ndarray:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        rng = np.random.default_rng(int.from_bytes(h[:8], "big"))
        v = rng.normal(size=self._dim).astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-9)

    def encode_batch(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        return np.stack([self.encode_one(t) for t in texts])
