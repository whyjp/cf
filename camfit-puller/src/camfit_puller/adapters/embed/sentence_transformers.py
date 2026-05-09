"""Adapter wrapping sentence-transformers (Korean-tuned models)."""
from __future__ import annotations
import numpy as np


class KoSrobertaEmbedder:
    model_name = "jhgan/ko-sroberta-multitask"

    def __init__(self, model_id: str | None = None, device: str = "cpu"):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_id or self.model_name, device=device)

    @property
    def dim(self) -> int:
        return int(self._model.get_sentence_embedding_dimension())

    def encode_one(self, text: str) -> np.ndarray:
        v = self._model.encode([text], normalize_embeddings=True)[0]
        return np.asarray(v, dtype=np.float32)

    def encode_batch(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        v = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return np.asarray(v, dtype=np.float32)
