"""Use-case: extract camfit-native-filter concept signals.

Each camp has a `collections` list (camfit's themes/curations applied to the camp).
The filter_concept_mapping table maps each filter name to (concept_id, polarity).
This use-case walks each camp's collections and writes signed signals.
"""
from __future__ import annotations
from dataclasses import dataclass

from ..ports.repo import CampReader, FilterConceptMappingRepository, FilterSignalWriter


@dataclass
class ExtractCamfitFilterSignals:
    camp_reader: CampReader
    mapping_repo: FilterConceptMappingRepository
    signal_writer: FilterSignalWriter

    def execute(self) -> int:
        n = 0
        for camp in self.camp_reader.iter_all():
            self.signal_writer.reset_for(camp.id)
            for filter_id in camp.collections:
                for concept_id, polarity in self.mapping_repo.for_filter(filter_id):
                    self.signal_writer.upsert(
                        camp.id, concept_id, float(polarity),
                        evidence=f"camfit_filter:{filter_id}",
                    )
                    n += 1
        return n
