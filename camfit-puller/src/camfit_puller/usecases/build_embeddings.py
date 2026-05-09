"""Use-case: build embeddings for every camp's `embed_text`.

Reads camps + their top reviews, generates the canonical embedding text
(domain.embed_text.build_embed_text), then encodes via the configured Embedder
and upserts into the VectorIndex.

Idempotent: same camp + unchanged text_hash → re-upsert with new created_at
(simple semantics; PgvectorIndex doesn't currently skip; trade-off accepted
for v1).
"""
from __future__ import annotations
from dataclasses import dataclass

from ..domain.embed_text import build_embed_text, text_hash
from ..ports.repo import CampReader, ReviewReader
from ..ports.embed import Embedder
from ..ports.vector import VectorIndex


@dataclass
class BuildEmbeddings:
    camp_reader: CampReader
    review_reader: ReviewReader
    embedder: Embedder
    vector_index: VectorIndex
    batch_size: int = 32

    def execute(self) -> int:
        ids: list[str] = []
        texts: list[str] = []
        for camp in self.camp_reader.iter_all():
            top = list(self.review_reader.top_for(camp.id, n=5))
            text = build_embed_text(camp, top)
            ids.append(camp.id)
            texts.append(text)
        if not ids:
            return 0
        vecs = self.embedder.encode_batch(texts, batch_size=self.batch_size)
        items = [(cid, vecs[i], text_hash(texts[i])) for i, cid in enumerate(ids)]
        return self.vector_index.upsert_many(items)
