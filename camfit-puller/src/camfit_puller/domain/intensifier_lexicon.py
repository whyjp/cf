"""Korean review intensifier lexicon — auto-derived from corpus.

Source: analysis of 1085 positive sentences (totalScore >= 62.0, ~p80)
and 451 negative sentences (totalScore <= 54.5, ~p20) from
data/reviews/*.json (154 files, all available).

NOTE: review totalScore is a composite operational score (range ~35-70),
not a raw sentiment score.  Polarity clusters use relative p20/p80 percentile
thresholds, not absolute cut-offs.

Re-runnable via scripts/derive_lexicon.py (created in T23.5).

Used by HeuristicNegationExtractor (T24) to compute temperature-weighted
review signals (T26 ExtractReviewSignals).
"""
from __future__ import annotations

# Top intensifiers consistently appearing in HIGH-SCORE reviews (>= p80)
# Listed by sentence-frequency (descending) — order is informational
INTENSIFIER_POSITIVE: tuple[str, ...] = (
    "정말",
    "진짜",
    "깔끔",
    "만족",
    "추천",
    "최고",
    "청결",
    "아주",
    "편안",
    "불편",
    "매우",
    "완전",
    "강추",
    "진심",
    "편리",
    "굉장히",
    "완벽",
    "대박",
    "아늑",
)

# Top intensifiers consistently appearing in LOW-SCORE reviews (<= p20)
# NOTE: corpus is positive-skewed; even low-score reviews contain praise.
# These tokens were statistically dominant in the low-score cluster.
INTENSIFIER_NEGATIVE: tuple[str, ...] = (
    "넘",
    "짱",
    "후회",
    "넘넘",
    "아쉽",
)

# Stats from derivation run (informational)
STATS = {
    "files_sampled": 154,
    "positive_sentences": 1085,
    "negative_sentences": 451,
    "p80_threshold": 62.0,
    "p20_threshold": 54.5,
    "model": "agent-derived 2026-05-09",
}
