"""Use-case: corpus-driven synonym discovery for a featured axis.

Bootstrapping problem: the boolean-axis registry (`domain.featured_axes`)
needs hand-curated keyword lists. Some Korean colloquial variants are easy
to miss — e.g. 방방/방방이 for trampoline. Hand-curating every variant for
every axis doesn't scale.

This use-case mines the actual camp corpus to surface candidate synonyms:

  1. Pick a seed token from the axis (default: the first keyword whose
     embedding the corpus has the most signal for — usually a unique,
     unambiguous term like "트램펄린" or "할로윈").
  2. Find every camp where the seed (or any other axis keyword) appears
     literally in description / brief / review text.
  3. Concatenate that subcorpus and extract Korean n-grams (length 2-5).
  4. Embed each candidate via ko-sroberta.
  5. Cosine-sort against the seed embedding; report top-N.

Output is a Markdown file (`data/synonyms_<axis>.md`) for human review,
NOT auto-merged into the registry. False-positive risk dictates a curator
loop — the report is the recommendation, FEATURED_AXES the decision.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np

from ..domain.featured_axes import FEATURED_AXES
from ..ports.embed import Embedder
from ..ports.repo import CampReader, ReviewReader


_KOREAN_NGRAM = re.compile(r"[가-힣]{2,5}")


def _candidate_tokens(text: str, min_count: int = 2) -> Counter:
    """Korean 2-5 char n-grams, lowercased, with corpus frequency.

    Pure-Hangul filter drops English/numbers/punct. min_count filters
    one-off mentions; common discourse particles still leak through but
    the cosine-similarity stage downranks them naturally.
    """
    counts = Counter(m.group() for m in _KOREAN_NGRAM.finditer(text))
    return Counter({t: n for t, n in counts.items() if n >= min_count})


@dataclass
class DiscoverSynonyms:
    camp_reader: CampReader
    review_reader: ReviewReader
    embedder: Embedder

    def execute(self, axis_id: str, *,
                top_k: int = 50,
                min_cosine: float = 0.55,
                min_count: int = 2,
                out_dir: Path | None = None) -> Path:
        axis = next((a for a in FEATURED_AXES if a["id"] == axis_id), None)
        if axis is None:
            raise ValueError(
                f"axis '{axis_id}' not in FEATURED_AXES — known: "
                f"{[a['id'] for a in FEATURED_AXES]}"
            )

        # 1) Find every camp whose text mentions ANY of the axis keywords.
        #    The literal-keyword scan happens against (description + brief +
        #    every review text). Keywords are lowercased; corpus is too.
        kws = [k.lower() for k in axis["keywords"]]
        seed_kw = axis["keywords"][0]  # first keyword = canonical seed
        camp_texts: list[str] = []
        for camp in self.camp_reader.iter_all():
            blob_parts: list[str] = [
                (camp.description or "").lower(),
                (camp.brief or "").lower(),
            ]
            for rv in self.review_reader.iter_for(camp.id):
                blob_parts.append((rv.text or "").lower())
            blob = " ".join(blob_parts)
            if any(k in blob for k in kws):
                camp_texts.append(blob)

        if not camp_texts:
            raise RuntimeError(
                f"No camps mention any keyword for axis '{axis_id}' — "
                f"either keywords are misspelled or the corpus is empty."
            )

        # 2) Token candidates from the matched subcorpus.
        joined = " ".join(camp_texts)
        candidates = _candidate_tokens(joined, min_count=min_count)
        # Drop tokens that ARE current keywords (we want NEW synonyms).
        existing = {k.lower() for k in axis["keywords"]}
        candidates = Counter({t: n for t, n in candidates.items() if t not in existing})
        if not candidates:
            raise RuntimeError("No new candidate tokens found.")

        # 3) Embed seed + every candidate. encode_batch is the hot path —
        #    a single GPU/CPU pass over the whole token list.
        tokens = list(candidates.keys())
        seed_vec = self.embedder.encode_batch([seed_kw])[0]
        cand_vecs = self.embedder.encode_batch(tokens, batch_size=128)
        # ko-sroberta normalizes; cosine == dot.
        sims = cand_vecs @ seed_vec
        order = np.argsort(-sims)

        # 4) Build the markdown report.
        out_dir = out_dir or Path("data")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"synonyms_{axis_id}.md"
        lines: list[str] = []
        lines.append(f"# Synonym candidates for axis `{axis_id}` ({axis['ko']})")
        lines.append("")
        lines.append(f"- seed: `{seed_kw}`")
        lines.append(f"- subcorpus: {len(camp_texts)} camps where any current keyword appears")
        lines.append(f"- candidates evaluated: {len(tokens)}")
        lines.append(f"- threshold: cosine ≥ {min_cosine}")
        lines.append("")
        lines.append("Above threshold (worth reviewing — paste into FEATURED_AXES keywords):")
        lines.append("")
        lines.append("| sim | freq | token |")
        lines.append("|----:|-----:|-------|")
        kept = 0
        for idx in order:
            sim = float(sims[idx])
            if sim < min_cosine:
                break
            tok = tokens[idx]
            freq = candidates[tok]
            lines.append(f"| {sim:.3f} | {freq:>4} | `{tok}` |")
            kept += 1
            if kept >= top_k:
                break
        if kept == 0:
            lines.append("| — | — | _no candidates above threshold_ |")
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return out_path
