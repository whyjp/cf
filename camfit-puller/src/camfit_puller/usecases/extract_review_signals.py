"""Use-case: extract review-derived concept signals with **temperature-weighted** scoring.

Per addendum (D2 management quality, D3 view satisfaction):
- Each review sentence yields ±1 polarity per concept (HeuristicNegationExtractor).
- Sentence sentiment INTENSITY is `1.0 + 0.5 × intensifier_count` capped at 2.0.
  Intensifier tokens come from domain.intensifier_lexicon (T23.5, agent-derived).
- Per-concept aggregate score: Σ(intensity × polarity) / Σ|intensity|, in [-1, +1].

Compared to a naive `(pos - neg) / total` formula, this gives:
- More weight to strongly-worded reviews ("정말 너무 좋아요!" — intensity 2.0)
- Less weight to mild mentions ("괜찮아요" — intensity 1.0)
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass

from ..ports.repo import ReviewReader, ReviewSignalWriter
from ..ports.extract import NegationAwareExtractor
from ..domain.intensifier_lexicon import INTENSIFIER_POSITIVE, INTENSIFIER_NEGATIVE


_INTENSIFIER_TOKENS: tuple[str, ...] = INTENSIFIER_POSITIVE + INTENSIFIER_NEGATIVE
_MAX_INTENSITY: float = 2.0
_BASE_INTENSITY: float = 1.0
_INTENSIFIER_BOOST: float = 0.5


def _sentence_intensity(sentence: str) -> float:
    """Returns 1.0..2.0. Counts ANY intensifier token (positive OR negative)
    occurrences and applies +0.5 per match capped at +1.0 above base."""
    if not sentence:
        return _BASE_INTENSITY
    count = sum(1 for tok in _INTENSIFIER_TOKENS if tok in sentence)
    return min(_MAX_INTENSITY, _BASE_INTENSITY + _INTENSIFIER_BOOST * count)


@dataclass
class ExtractReviewSignals:
    review_reader: ReviewReader
    extractor: NegationAwareExtractor
    signal_writer: ReviewSignalWriter

    def execute(self, camp_id: str) -> int:
        # Per-concept accumulators
        agg: dict[str, dict] = defaultdict(lambda: {
            "weighted_sum": 0.0,    # Σ(intensity × polarity)
            "intensity_sum": 0.0,   # Σ|intensity|
            "pos_count": 0,
            "neg_count": 0,
            "evidence": "",
        })
        for rv in self.review_reader.iter_for(camp_id):
            for cid, pol, snippet in self.extractor.extract_with_polarity(rv.text or ""):
                intensity = _sentence_intensity(snippet)
                a = agg[cid]
                a["weighted_sum"] += intensity * pol
                a["intensity_sum"] += intensity
                if pol > 0:
                    a["pos_count"] += 1
                else:
                    a["neg_count"] += 1
                if not a["evidence"]:
                    a["evidence"] = snippet
        self.signal_writer.reset_for(camp_id)
        n = 0
        for cid, a in agg.items():
            denom = a["intensity_sum"] or 1.0
            score = a["weighted_sum"] / denom  # in [-2, +2] technically; clip to [-1, 1]
            score = max(-1.0, min(1.0, score))
            self.signal_writer.upsert(
                camp_id, cid, score, a["pos_count"], a["neg_count"], a["evidence"],
            )
            n += 1
        return n
