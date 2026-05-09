"""Use-case: ingest a snapshot from a DataSource into PG.

Walk every summary, fetch detail (preferred over summary), upsert. Walk reviews
per camp. Walk filters (camfit native taxonomy)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from ..ports.repo import CampWriter, ReviewWriter, CamfitFilterRepository
from ..ports.source import DataSource


@dataclass
class IngestSnapshot:
    source: DataSource
    camp_writer: CampWriter
    review_writer: ReviewWriter
    filter_repo: CamfitFilterRepository

    def execute(self) -> tuple[int, int, int]:
        """Returns (camps_n, reviews_n, filters_n)."""
        camp_ids: list[str] = []
        camps_n = 0
        for summary in self.source.iter_summaries():
            detail = self.source.get_detail(summary.id) or summary
            self.camp_writer.upsert_many([detail])
            camp_ids.append(summary.id)
            camps_n += 1

        reviews_n = 0
        for cid in camp_ids:
            batch: list = []
            for rv in self.source.iter_reviews(cid):
                batch.append(rv)
            if batch:
                self.review_writer.upsert_many(batch)
                reviews_n += len(batch)

        filters_n = 0
        for fid, name, kind, raw in self.source.iter_filters():
            self.filter_repo.upsert(fid, name, kind, raw)
            filters_n += 1

        return camps_n, reviews_n, filters_n
