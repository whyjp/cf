"""Deterministic mock concept extractor — substring match.

Useful for unit tests where you want to isolate use-case logic from real
embedding similarity.
"""
from __future__ import annotations


class MockConceptExtractor:
    def __init__(self, vocab_concepts):
        self._vocab = vocab_concepts

    def vocabulary(self):
        return list(self._vocab)

    def extract(self, text, vector=None, top_k=10, min_score=0.3):
        out = []
        for c in self._vocab:
            if c.name in text:
                out.append((c.id, 1.0))
            elif any(part in text for part in c.name.split()):
                out.append((c.id, 0.5))
        return [x for x in out if x[1] >= min_score][:top_k]
