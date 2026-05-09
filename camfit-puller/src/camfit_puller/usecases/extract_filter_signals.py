"""Use-case: extract camfit-native-filter concept signals.

Each camp has a `collections` list (camfit's themes/curations applied to the camp).
The filter_concept_mapping table maps each filter name to (concept_id, polarity).
This use-case walks each camp's collections and writes signed signals.

Idempotent: reset_for(camp_id) wipes prior signals before re-writing.

Parallelism: `workers > 1` fans the per-camp work out across a thread pool;
each worker borrows a PG connection per call, so concurrency is bounded by
the pool size.  iter_all() yields each camp once → no two workers touch the
same camp_id, so reset_for + upsert is race-free.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from ..ports.repo import CampReader, FilterConceptMappingRepository, FilterSignalWriter


@dataclass
class ExtractCamfitFilterSignals:
    camp_reader: CampReader
    mapping_repo: FilterConceptMappingRepository
    signal_writer: FilterSignalWriter

    def execute(self, *, workers: int = 1) -> int:
        camps = list(self.camp_reader.iter_all())
        if not camps:
            return 0
        workers = max(1, min(workers, 8))

        def _one(camp) -> int:
            self.signal_writer.reset_for(camp.id)
            n = 0
            for filter_id in camp.collections:
                for concept_id, polarity in self.mapping_repo.for_filter(filter_id):
                    self.signal_writer.upsert(
                        camp.id, concept_id, float(polarity),
                        evidence=f"camfit_filter:{filter_id}",
                    )
                    n += 1
            return n

        if workers == 1:
            return sum(_one(c) for c in camps)

        total = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(_one, c) for c in camps]
            for f in as_completed(futs):
                total += f.result()
        return total
