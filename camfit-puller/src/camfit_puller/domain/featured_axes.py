"""Featured axis registry — boolean shortcut filters surfaced as 대표축 chips.

Each axis is keyword-matched (case-insensitive substring) against the union
of camp.collections + types + facilities + location_types + hashtags +
description + brief. Adding a new axis is a one-entry append below; the
backend re-derives `r.has_<id>` per request and the FE picks up new chip
metadata on its next /featured-axes fetch.

Spec: docs/superpowers/specs/2026-05-09-featured-axes-registry-design.md
"""
from __future__ import annotations
from typing import TypedDict


class FeaturedAxis(TypedDict):
    id: str            # snake_case, becomes r.has_<id>
    ko: str            # display label (Korean)
    icon: str          # emoji
    tone: str          # "" | "warm" | "bark" — chip color family
    keywords: list[str]  # case-insensitive substring matches (mixed en/ko)


FEATURED_AXES: list[FeaturedAxis] = [
    {"id": "valley",     "ko": "계곡",     "icon": "🌊", "tone": "",
     "keywords": ["valley", "계곡"]},
    {"id": "kids",       "ko": "키즈캠핑", "icon": "🧒", "tone": "warm",
     "keywords": ["kids", "키즈", "아이"]},
    {"id": "trampoline", "ko": "트램펄린", "icon": "🤸", "tone": "bark",
     # "방방" is the Korean colloquial standard ("방방이" via substring) — most
     # camp reviews use it instead of the formal "트램펄린". 4 spelling
     # variants of 트램펄린/트램폴린 are out there; cover them all.
     "keywords": ["trampoline", "trampolin",
                  "트램펄린", "트램폴린", "트렘펄린", "트렘폴린",
                  "방방"]},
    {"id": "halloween",  "ko": "할로윈",   "icon": "🎃", "tone": "warm",
     "keywords": ["할로윈", "핼러윈", "핼로윈", "halloween"]},
    {"id": "cherry",     "ko": "벚꽃",     "icon": "🌸", "tone": "warm",
     "keywords": ["벚꽃", "벚나무"]},
    {"id": "autumn",     "ko": "단풍",     "icon": "🍁", "tone": "bark",
     "keywords": ["단풍"]},
]


# Module-level invariants — fail-fast at import.
assert len({a["id"] for a in FEATURED_AXES}) == len(FEATURED_AXES), \
    "FEATURED_AXES has duplicate id"
for _a in FEATURED_AXES:
    assert _a["keywords"], f"FEATURED_AXES['{_a['id']}'] has empty keywords"
    assert _a["tone"] in ("", "warm", "bark"), \
        f"FEATURED_AXES['{_a['id']}'] has invalid tone {_a['tone']!r}"
del _a
