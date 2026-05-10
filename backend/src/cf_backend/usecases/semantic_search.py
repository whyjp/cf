"""Use-case: semantic search — query string → ranked Camp list.

Pipeline:
  q (str) → embedder.encode_one → vector_index.knn → camp_reader.list_filtered(ids)

Order from KNN is preserved (camps re-sorted to match knn order, not the order
the reader happens to return them in).
"""
from __future__ import annotations
from dataclasses import dataclass

from ..domain.models import Camp
from ..ports.embed import Embedder
from ..ports.vector import VectorIndex
from ..ports.repo import CampReader


@dataclass
class SemanticSearch:
    embedder: Embedder
    vector_index: VectorIndex
    camp_reader: CampReader

    def execute(self, q: str, k: int = 20) -> list[Camp]:
        v = self.embedder.encode_one(q)
        hits = self.vector_index.knn(v, k=k)
        if not hits:
            return []
        ids = [cid for cid, _ in hits]
        camps_by_id = {c.id: c for c in self.camp_reader.list_filtered(ids=ids)}
        # Preserve KNN order
        return [camps_by_id[cid] for cid, _ in hits if cid in camps_by_id]
