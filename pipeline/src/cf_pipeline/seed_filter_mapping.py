"""Seed the `camfit_filters` + `filter_concept_mapping` tables.

Each row maps a camfit native filter (theme/collection/badge/inventory_filter)
to a concept_id with polarity (+1 affirms, -1 negates).

This is the camfit-native taxonomy bridge — when a camp's `collections` list
contains "키즈캠핑장", the ExtractCamfitFilterSignals use-case looks it up here
and writes a +1 signal for the `kids` concept.

Curate this list by hand. Update when camfit adds new themes/collections.
"""
from __future__ import annotations
import sys

from cf_be_api.settings import Settings
from cf_be_api.container import Container
from cf_be_api.domain.models import Concept
from rich.console import Console


# (filter_id, name, kind, concept_id, polarity)
# filter_id == name for camfit's text-named themes/collections (no separate ID).
# Add new entries when new themes/collections appear in the corpus.
MAPPINGS: list[tuple[str, str, str, str, int]] = [
    # ── Themes (from /v1/themes) ────────────────────────────────────
    ("테마:대형견과함께",     "테마:대형견과함께",     "theme",      "pets",        +1),
    ("테마:찾아오는체험",     "테마:찾아오는체험",     "theme",      "stargazing",  +1),  # placeholder; refine
    ("테마:인기급상승",       "테마:인기급상승",       "theme",      "popular",     +1),  # need 'popular' concept
    ("테마:파인스테이",       "테마:파인스테이",       "theme",      "private",     +1),
    ("테마:#인별맛집",        "테마:#인별맛집",        "theme",      "photogenic",  +1),  # need 'photogenic' concept
    ("테마:뷰 맛집",          "테마:뷰 맛집",          "theme",      "oceanview",   +1),  # one of view-* concepts
    # ── Collections (from /v1/collections) ──────────────────────────
    ("키즈캠핑장",           "키즈캠핑장",           "collection", "kids",        +1),
    ("노키즈캠핑장",         "노키즈캠핑장",         "collection", "kids",        -1),  # the polarity-flip case
    ("계곡캠핑장",           "계곡캠핑장",           "collection", "valley",      +1),
    ("리버뷰 캠핑장",         "리버뷰 캠핑장",         "collection", "riverview",   +1),
    ("오션뷰 캠핑장",         "오션뷰 캠핑장",         "collection", "oceanview",   +1),
    ("프라이빗 캠핑장",       "프라이빗 캠핑장",       "collection", "private",     +1),
    ("반려견 동반",           "반려견 동반",           "collection", "pets",        +1),
    ("반려동물 입장 불가",    "반려동물 입장 불가",    "collection", "pets",        -1),
    ("Early Checkin ☀️",     "Early Checkin ☀️",     "collection", "early_checkin", +1),
    ("개별 샤워실/화장실",    "개별 샤워실/화장실",    "collection", "private_bathroom", +1),
    ("달과 별이 잘 보이는 캠핑장", "달과 별이 잘 보이는 캠핑장", "collection", "stargazing", +1),
    ("충주호",               "충주호",               "collection", "lakeview",    +1),
    ("2025 캠핏 어워드",     "2025 캠핏 어워드",     "collection", "award",       +1),  # need 'award' concept
    ("혼자 캠핑가기 좋은 날 🎒", "혼자 캠핑가기 좋은 날 🎒", "collection", "solo",      +1),  # need 'solo' concept
]

# Auxiliary concepts that aren't in concept_seeds.py but are referenced above.
# These get inserted as `source="manual"` in the concepts table so the FK in
# filter_concept_mapping can resolve.
EXTRA_CONCEPTS: list[tuple[str, str, str]] = [
    # (id, name, category)
    ("popular",          "인기",          "vibe"),
    ("photogenic",       "포토제닉",      "vibe"),
    ("award",            "어워드",        "vibe"),
    ("solo",             "솔로캠핑",      "audience"),
    ("early_checkin",    "얼리체크인",    "service"),
    ("private_bathroom", "개별 화장실",   "facility"),
]


def main() -> int:
    console = Console()
    s = Settings(embedder="mock")
    c = Container(s)

    # 1. Ensure auxiliary concepts exist
    for cid, name, category in EXTRA_CONCEPTS:
        c.concept_repo.upsert_concept(
            Concept(id=cid, name=name, source="manual", category=category)
        )

    # 2. Upsert each filter row
    for fid, fname, fkind, _cid, _pol in MAPPINGS:
        c.filter_repo.upsert(fid, fname, fkind, None)

    # 3. Upsert each mapping
    for fid, _fname, _fkind, cid, polarity in MAPPINGS:
        c.mapping_repo.upsert_mapping(fid, cid, polarity)

    n_filters = len(c.filter_repo.all())
    console.print(f"[seed_filter_mapping] camfit_filters: {n_filters}")
    console.print(f"[seed_filter_mapping] filter_concept_mapping rows: {len(MAPPINGS)}")
    console.print(f"[seed_filter_mapping] EXTRA_CONCEPTS upserted: {len(EXTRA_CONCEPTS)}")

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
