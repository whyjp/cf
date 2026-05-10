"""Heuristic Korean negation-aware concept extractor.

Scans text sentence-by-sentence. For each concept name found:
  - if a negation token appears within NEG_WINDOW_CHARS of the concept word →
    polarity = -1
  - else → polarity = +1
Returns list of (concept_id, polarity, evidence_snippet).

Negation tokens cover common Korean patterns:
  - 불가 / 금지 / 안됨 / 안돼 / 사절 / 없음
  - 노X / no-X
  - 받지 않 / 허용 안

Lexicon for *intensity* (temperature-weighted scoring) lives in
domain.intensifier_lexicon — used by ExtractReviewSignals (T26), NOT here.
This adapter only emits ±1 polarity. Temperature aggregation is the use-case's
job, where it can apply intensifier counts to derive a magnitude score.
"""
from __future__ import annotations
import re
from typing import Iterable

from ...ports.repo import ConceptRepository


NEG_TOKENS: tuple[str, ...] = (
    "불가", "금지", "안됨", "안 돼", "안돼", "사절", "없음", "없습니다",
    "안 되", "안되", "받지 않", "허용 안", "노키즈", "노-키즈", "노 키즈",
    "출입 제한", "입장 제한", "안받",
)
NEG_WINDOW_CHARS: int = 16

_SENT_SPLIT = re.compile(r"(?<=[\.\!\?。\?\!])\s+|\n+")


class HeuristicNegationExtractor:
    """Implements ports.extract.NegationAwareExtractor.

    Vocabulary (concept names) is loaded once from the repo and reused.
    Call `invalidate()` if you add concepts mid-session.
    """

    def __init__(self, concept_repo: ConceptRepository):
        self._repo = concept_repo
        self._concepts: list | None = None

    def invalidate(self) -> None:
        self._concepts = None

    def _load(self):
        if self._concepts is None:
            self._concepts = list(self._repo.all())
        return self._concepts

    def extract_with_polarity(self, text: str) -> list[tuple[str, int, str]]:
        out: list[tuple[str, int, str]] = []
        if not text:
            return out
        # Split into sentences for window scoping
        for sent in _SENT_SPLIT.split(text):
            sent = sent.strip()
            if not sent:
                continue
            for c in self._load():
                idx = sent.find(c.name)
                if idx < 0:
                    continue
                window_start = max(0, idx - NEG_WINDOW_CHARS)
                window_end = idx + len(c.name) + NEG_WINDOW_CHARS
                window = sent[window_start:window_end]
                pol = -1 if any(t in window for t in NEG_TOKENS) else 1
                out.append((c.id, pol, sent[:140]))
        return out
