"""KeyBERT-style concept extractor — cosine similarity between text vector
and pre-computed vocabulary vectors. Returns top-K concept ids above min_score."""
from __future__ import annotations
import numpy as np

from ...domain.models import Concept
from ...ports.repo import ConceptRepository
from ...ports.embed import Embedder


class KeyBertExtractor:
    """Implements ports.extract.ConceptExtractor.

    Vocabulary is loaded lazily from `concept_repo.all()` and cached. If the
    underlying vocabulary changes (new seeds added), call `invalidate()` to refresh.
    """

    def __init__(self, embedder: Embedder, concept_repo: ConceptRepository):
        self._emb = embedder
        self._repo = concept_repo
        self._vocab: list[Concept] = []
        self._vocab_vecs: np.ndarray | None = None

    def invalidate(self) -> None:
        self._vocab = []
        self._vocab_vecs = None

    def vocabulary(self) -> list[Concept]:
        if not self._vocab:
            self._vocab = list(self._repo.all())
            if self._vocab:
                self._vocab_vecs = self._emb.encode_batch([c.name for c in self._vocab])
        return self._vocab

    def extract(self, text: str, vector: np.ndarray | None = None,
                top_k: int = 10, min_score: float = 0.3) -> list[tuple[str, float]]:
        vocab = self.vocabulary()
        if not vocab or self._vocab_vecs is None:
            return []
        if vector is None:
            vector = self._emb.encode_one(text)
        # cosine sim. Both sides are L2-normalized by the embedder, so dot is enough,
        # but keep general formula in case a custom embedder isn't normalized.
        denom = (np.linalg.norm(self._vocab_vecs, axis=1) * np.linalg.norm(vector)) + 1e-9
        sims = (self._vocab_vecs @ vector) / denom
        order = np.argsort(-sims)
        out: list[tuple[str, float]] = []
        for i in order:
            score = float(sims[i])
            if score < min_score:
                break
            out.append((vocab[i].id, score))
            if len(out) >= top_k:
                break
        return out
