"""Use-case: seed concept vocabulary + auto-derive from existing camp data.

Idempotent — re-running is safe (UPSERT behavior on the repo).
"""
from __future__ import annotations
import re
from dataclasses import dataclass

from ..domain.concept_seeds import SEEDS
from ..domain.models import Concept
from ..ports.repo import CampReader, ConceptRepository


_SLUG_RE = re.compile(r"[^a-zA-Z0-9가-힣]+")


def _slug(name: str) -> str:
    return _SLUG_RE.sub("_", name).strip("_").lower()


@dataclass
class BuildVocabulary:
    camp_reader: CampReader
    concept_repo: ConceptRepository

    def execute(self) -> int:
        n = 0
        # 1) Curated seeds
        seed_names: set[str] = {name for _, name, *_ in SEEDS}
        for cid, name, category, is_axis in SEEDS:
            self.concept_repo.upsert_concept(
                Concept(id=cid, name=name, source="manual",
                        category=category, is_axis=is_axis)
            )
            n += 1
        # 2) Auto-derived from camp hashtags + facilities
        # Track both id slugs and names to avoid UNIQUE(name) collisions with seeds.
        seen: set[str] = {cid for cid, *_ in SEEDS}
        seen_names: set[str] = set(seed_names)
        for camp in self.camp_reader.iter_all():
            for h in camp.hashtags:
                slug = "h_" + _slug(h)
                if slug in seen or h in seen_names:
                    continue
                seen.add(slug)
                seen_names.add(h)
                self.concept_repo.upsert_concept(
                    Concept(id=slug, name=h, source="hashtag")
                )
                n += 1
            for f in (camp.facilities + camp.additional_facilities):
                slug = "f_" + _slug(f)
                if slug in seen or f in seen_names:
                    continue
                seen.add(slug)
                seen_names.add(f)
                self.concept_repo.upsert_concept(
                    Concept(id=slug, name=f, source="facility")
                )
                n += 1
        return n
