"""Use-case: fetch enriched detail payload for a single camp.

Aggregates: Camp summary + top reviews + concepts + theme membership
into a single dict suitable for the API DetailPanel response.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from ..domain.models import Camp
from ..ports.repo import CampReader, ReviewReader, ConceptRepository, ThemeRepository
from ..domain.errors import CampNotFound


@dataclass
class GetSiteDetail:
    camp_reader: CampReader
    review_reader: ReviewReader
    concept_repo: ConceptRepository
    theme_repo: ThemeRepository

    def execute(self, camp_id: str, *, top_reviews_n: int = 3) -> dict:
        camp = self.camp_reader.get(camp_id)
        if camp is None:
            raise CampNotFound(camp_id)

        reviews = self.review_reader.top_for(camp_id, n=top_reviews_n, sort="score")
        total_reviews = self.review_reader.total_for(camp_id)
        concepts = self.concept_repo.for_camp(camp_id)
        theme = self.theme_repo.for_camp(camp_id)

        return {
            "camp": camp.model_dump(),
            "reviews_top": [r.model_dump() for r in reviews],
            "reviews_total": total_reviews,
            "concepts": [
                {"id": cc.concept_id, "score": cc.score} for cc in concepts
            ],
            "theme": (
                {"id": theme.id, "label": theme.label, "member_count": theme.member_count}
                if theme else None
            ),
        }
