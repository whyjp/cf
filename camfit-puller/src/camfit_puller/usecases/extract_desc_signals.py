"""Use-case: extract description-derived concept signals via KeyBERT.

Reads each camp's `embed_text` (camp + top reviews → text), embeds it,
then asks the ConceptExtractor for top-K concepts above min_score.
Writes to camp_desc_signals (always positive — semantic similarity has
no notion of negation).

Idempotent: reset_for(camp_id) wipes prior signals before re-writing.
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

    def execute(self, *, top_k: int = 10, min_score: float = 0.3) -> int:
        n = 0
        for camp in self.camp_reader.iter_all():
            top = list(self.review_reader.top_for(camp.id, n=5))
            text = build_embed_text(camp, top)
            v = self.embedder.encode_one(text)
            self.signal_writer.reset_for(camp.id)
            for cid, score in self.extractor.extract(text, v, top_k=top_k, min_score=min_score):
                self.signal_writer.upsert(camp.id, cid, float(score))
                n += 1
        return n
