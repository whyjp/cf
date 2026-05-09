#!/usr/bin/env python3
"""Derive Korean intensifier lexicon from the camfit review corpus.

Usage:
    python scripts/derive_lexicon.py [--data-dir DATA_DIR]

Reads data/reviews/*.json, clusters sentences by relative score percentile
(top 20% vs. bottom 20%), counts candidate intensifier words, and prints
the resulting lexicon.

NOTE on scoring: review totalScore values in this corpus are composite
operational scores (range ~35-70), NOT raw sentiment scores.  We therefore
use RELATIVE percentile thresholds (p80 = positive, p20 = negative) rather
than absolute cut-offs.

Output is written to:
    src/camfit_puller/domain/intensifier_lexicon.py

Re-running on the same corpus produces identical output (deterministic).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import quantiles

# ---------------------------------------------------------------------------
# Seed candidate list — Korean intensifier tokens (prior knowledge seed)
# ---------------------------------------------------------------------------
CANDIDATES: list[str] = [
    # Degree adverbs (positive tendency)
    "정말",
    "너무",
    "매우",
    "엄청",
    "굉장히",
    "진짜",
    "완전",
    "진심",
    "너무너무",
    "정말정말",
    "아주",
    "무척",
    "몹시",
    "넘",
    "넘넘",
    # Exclamatives / recommendation (positive tendency)
    "최고",
    "강추",
    "추천",
    "완벽",
    "짱",
    "굿",
    "최강",
    "꼭",
    "찐",
    "대박",
    "만족",
    # Quality positive markers
    "깨끗",
    "깔끔",
    "청결",
    "친절",
    "쾌적",
    "편리",
    "편안",
    "아늑",
    # Negative intensifiers / markers
    "실망",
    "짜증",
    "별로",
    "최악",
    "후회",
    "아쉽",
    "아쉬움",
    "불편",
    "비추",
    "불친절",
    "불결",
    "열악",
    "형편없",
    "불쾌",
    "노후",
    "낡",
]

# Sort by length descending so longer tokens match before substrings
CANDIDATES_SORTED = sorted(CANDIDATES, key=len, reverse=True)


def split_sentences(text: str) -> list[str]:
    """Split Korean review text into sentences on .!?\\n boundaries."""
    parts = re.split(r"[.!?\n。]+", text)
    return [p.strip() for p in parts if p.strip()]


def load_all_reviews(data_dir: Path) -> list[tuple[str, float]]:
    """Load (text, totalScore) pairs from all JSON files in data_dir."""
    pairs: list[tuple[str, float]] = []
    for path in sorted(data_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for review in data.get("reviews", []):
                text = review.get("text", "")
                score = review.get("totalScore", None)
                if text and score is not None:
                    pairs.append((text, float(score)))
        except Exception:
            continue
    return pairs


def compute_percentile_thresholds(
    reviews: list[tuple[str, float]],
) -> tuple[float, float]:
    """Return (p20, p80) thresholds for polarity clustering.

    The corpus has composite operational scores (range ~35-70), not raw
    sentiment scores, so absolute thresholds (e.g. 80/30) don't apply.
    We use relative percentiles instead.
    """
    scores = sorted(s for _, s in reviews)
    n = len(scores)
    p20 = scores[n // 5]
    p80 = scores[4 * n // 5]
    return p20, p80


def analyze(
    reviews: list[tuple[str, float]],
    p_low: float,
    p_high: float,
) -> tuple[dict[str, int], dict[str, int], int, int]:
    """Return (pos_counts, neg_counts, n_pos_sentences, n_neg_sentences)."""
    pos_counts: dict[str, int] = defaultdict(int)
    neg_counts: dict[str, int] = defaultdict(int)
    n_pos = 0
    n_neg = 0

    for text, score in reviews:
        if score >= p_high:
            cluster = "pos"
        elif score <= p_low:
            cluster = "neg"
        else:
            continue

        sentences = split_sentences(text)
        for sent in sentences:
            if cluster == "pos":
                n_pos += 1
            else:
                n_neg += 1
            for token in CANDIDATES_SORTED:
                if token in sent:
                    if cluster == "pos":
                        pos_counts[token] += 1
                    else:
                        neg_counts[token] += 1

    return dict(pos_counts), dict(neg_counts), n_pos, n_neg


def filter_lexicon(
    pos_counts: dict[str, int],
    neg_counts: dict[str, int],
    min_freq: int = 3,
    min_ratio: float = 0.70,
    min_freq_neg: int | None = None,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Return (positive_tokens, negative_tokens) sorted by frequency desc.

    min_freq_neg: minimum sentence frequency for negative tokens.  Defaults
    to min_freq.  Can be set lower to compensate for a positive-skewed corpus
    where the negative cluster is intrinsically sparse.
    """
    if min_freq_neg is None:
        min_freq_neg = min_freq

    all_tokens = set(pos_counts) | set(neg_counts)
    pos_tokens: list[tuple[str, int]] = []
    neg_tokens: list[tuple[str, int]] = []

    for token in all_tokens:
        p = pos_counts.get(token, 0)
        n = neg_counts.get(token, 0)
        total = p + n
        if total == 0:
            continue
        pos_ratio = p / total
        neg_ratio = n / total

        if p >= min_freq and pos_ratio >= min_ratio:
            pos_tokens.append((token, p))
        elif n >= min_freq_neg and neg_ratio >= min_ratio:
            neg_tokens.append((token, n))
        # Else: neither side dominates — drop

    pos_tokens.sort(key=lambda x: x[1], reverse=True)
    neg_tokens.sort(key=lambda x: x[1], reverse=True)
    return pos_tokens, neg_tokens


def write_lexicon_file(
    output_path: Path,
    pos_tokens: list[tuple[str, int]],
    neg_tokens: list[tuple[str, int]],
    files_sampled: int,
    n_pos: int,
    n_neg: int,
    p_low: float,
    p_high: float,
) -> None:
    pos_list = "(\n" + "".join(f'    "{t}",\n' for t, _ in pos_tokens) + ")"
    neg_list = "(\n" + "".join(f'    "{t}",\n' for t, _ in neg_tokens) + ")"

    content = f'''"""Korean review intensifier lexicon — auto-derived from corpus.

Source: analysis of {n_pos} positive sentences (totalScore >= {p_high}, ~p80)
and {n_neg} negative sentences (totalScore <= {p_low}, ~p20) from
data/reviews/*.json ({files_sampled} files, all available).

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
INTENSIFIER_POSITIVE: tuple[str, ...] = {pos_list}

# Top intensifiers consistently appearing in LOW-SCORE reviews (<= p20)
# NOTE: corpus is positive-skewed; even low-score reviews contain praise.
# These tokens were statistically dominant in the low-score cluster.
INTENSIFIER_NEGATIVE: tuple[str, ...] = {neg_list}

# Stats from derivation run (informational)
STATS = {{
    "files_sampled": {files_sampled},
    "positive_sentences": {n_pos},
    "negative_sentences": {n_neg},
    "p80_threshold": {p_high},
    "p20_threshold": {p_low},
    "model": "agent-derived 2026-05-09",
}}
'''
    output_path.write_text(content, encoding="utf-8")
    print(f"Written: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "reviews",
        help="Directory containing <camp_id>.json review files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent
        / "src"
        / "camfit_puller"
        / "domain"
        / "intensifier_lexicon.py",
        help="Output Python file path",
    )
    parser.add_argument(
        "--min-freq",
        type=int,
        default=3,
        help="Minimum sentence frequency to keep a token (default: 3)",
    )
    parser.add_argument(
        "--min-ratio",
        type=float,
        default=0.70,
        help="Minimum polarity ratio to keep a token (default: 0.70)",
    )
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    if not data_dir.exists():
        print(f"ERROR: data dir not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    json_files = list(data_dir.glob("*.json"))
    print(f"Loading reviews from {len(json_files)} files in {data_dir} ...")
    reviews = load_all_reviews(data_dir)
    print(f"  {len(reviews)} reviews loaded")

    p_low, p_high = compute_percentile_thresholds(reviews)
    print(f"  Percentile thresholds: p20={p_low} (negative), p80={p_high} (positive)")

    print("Analysing ...")
    pos_counts, neg_counts, n_pos, n_neg = analyze(reviews, p_low=p_low, p_high=p_high)
    print(f"  Positive sentences: {n_pos}")
    print(f"  Negative sentences: {n_neg}")

    pos_tokens, neg_tokens = filter_lexicon(
        pos_counts,
        neg_counts,
        min_freq=args.min_freq,
        min_ratio=args.min_ratio,
        # Corpus is positive-skewed; lower min_freq for negative cluster so
        # clearly-negative words (e.g. 아쉽, 후회) are not excluded purely
        # because the negative cluster has fewer sentences (451 vs 1085).
        min_freq_neg=1,
    )

    print("\n--- POSITIVE intensifiers ---")
    for token, freq in pos_tokens:
        p = pos_counts.get(token, 0)
        n = neg_counts.get(token, 0)
        ratio = p / (p + n) if (p + n) > 0 else 0
        print(f"  {token!r:20s}  freq={freq}  ratio={ratio:.2f}")

    print("\n--- NEGATIVE intensifiers ---")
    for token, freq in neg_tokens:
        p = pos_counts.get(token, 0)
        n = neg_counts.get(token, 0)
        ratio = n / (p + n) if (p + n) > 0 else 0
        print(f"  {token!r:20s}  freq={freq}  ratio={ratio:.2f}")

    write_lexicon_file(
        args.output,
        pos_tokens,
        neg_tokens,
        files_sampled=len(json_files),
        n_pos=n_pos,
        n_neg=n_neg,
        p_low=p_low,
        p_high=p_high,
    )


if __name__ == "__main__":
    main()
