"""Use-case: extract description-derived concept signals via KeyBERT.

Reads each camp's `embed_text` (camp + top reviews → text), embeds it,
then asks the ConceptExtractor for top-K concepts above min_score.
Writes to camp_desc_signals (always positive — semantic similarity has
no notion of negation).

Idempotent: reset_for(camp_id) wipes prior signals before re-writing.

Performance note: the embedder is invoked once with the full batch of
camp texts (sentence-transformers handles internal batching) instead of
once per camp.  KeyBERT extraction is then a per-camp numpy dot-product
against the cached vocabulary matrix, which is fast enough that no extra
parallelism is needed.  PG writes (reset + upserts) remain serial; they
are O(signals) and cheap.
"""
from __future__ import annotations
from dataclasses import dataclass

from ..domain.embed_text import build_embed_text
from ..ports.repo import CampReader, ReviewReader, DescSignalWriter
from ..ports.extract import ConceptExtractor
from ..ports.embed import Embedder


@dataclass
class ExtractDescSignals:
    camp_reader: CampReader
    review_reader: ReviewReader
    embedder: Embedder
    extractor: ConceptExtractor
    signal_writer: DescSignalWriter
    encode_batch_size: int = 64

    def execute(self, *, top_k: int = 10, min_score: float = 0.3) -> int:
        # Pass 1 — collect (camp, text) pairs.  Building the embed-text reads
        # the top-N reviews per camp from PG; each call uses one pooled
        # connection so this stays bounded by the pool size.
        camps = []
        texts: list[str] = []
        for camp in self.camp_reader.iter_all():
            top = list(self.review_reader.top_for(camp.id, n=5))
            camps.append(camp)
            texts.append(build_embed_text(camp, top))
        if not camps:
            return 0

        # Pass 2 — one batched encode call.  sentence-transformers handles
        # device/precision/batch-size internally; we just hand it everything.
        vecs = self.embedder.encode_batch(texts, batch_size=self.encode_batch_size)

        # Pass 3 — per-camp KeyBERT extraction (numpy dot product) + PG writes.
        n = 0
        for camp, text, v in zip(camps, texts, vecs):
            self.signal_writer.reset_for(camp.id)
            for cid, score in self.extractor.extract(
                text, v, top_k=top_k, min_score=min_score,
            ):
                self.signal_writer.upsert(camp.id, cid, float(score))
                n += 1
        return n
