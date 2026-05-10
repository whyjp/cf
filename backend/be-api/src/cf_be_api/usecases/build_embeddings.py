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

    def execute(self, *, ids: list[str] | None = None) -> int:
        """Build/refresh embeddings.

        Default (ids=None): every camp in PG (full rebuild).
        ids=[...]: only those camps (incremental — pair with ingest_camps --incremental's new_ids).
        Idempotent: same camp re-encoded if called again.
        """
        camp_iter = (
            self.camp_reader.iter_since(ids=ids)
            if ids
            else self.camp_reader.iter_all()
        )
        camp_ids: list[str] = []
        texts: list[str] = []
        for camp in camp_iter:
            top = list(self.review_reader.top_for(camp.id, n=5))
            text = build_embed_text(camp, top)
            camp_ids.append(camp.id)
            texts.append(text)
        if not camp_ids:
            return 0
        vecs = self.embedder.encode_batch(texts, batch_size=self.batch_size)
        items = [(cid, vecs[i], text_hash(texts[i])) for i, cid in enumerate(camp_ids)]
        return self.vector_index.upsert_many(items)
