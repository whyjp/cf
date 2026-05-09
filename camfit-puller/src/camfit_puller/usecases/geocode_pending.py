"""Use-case: geocode all camps that don't yet have lat/lon.

Reads camps where `camp.geo is None`, calls the Geocoder for each, persists via
CampWriter.set_geo(...). Idempotent — re-runs only those still missing geo.

Address-first policy (spec §5): we use camp.address (or fall back to
'sido sigungu' as a coarser hint) as the geocode query. NO coord fallback —
if the geocoder fails, the camp simply remains without coords.
"""
from __future__ import annotations
from dataclasses import dataclass

from ..ports.repo import CampReader, CampWriter
from ..ports.geocode import Geocoder


@dataclass
class GeocodePending:
    camp_reader: CampReader
    camp_writer: CampWriter
    geocoder: Geocoder

    def execute(self) -> dict:
        n_attempted = 0
        n_resolved = 0
        n_failed = 0
        for camp in self.camp_reader.iter_all():
            if camp.geo is not None:
                continue  # already geocoded
            n_attempted += 1
            query = self._build_query(camp)
            if not query:
                n_failed += 1
                continue
            point = self.geocoder.lookup(query)
            if point is None:
                n_failed += 1
                continue
            self.camp_writer.set_geo(camp.id, point.lat, point.lon)
            n_resolved += 1
        return {"attempted": n_attempted, "resolved": n_resolved, "failed": n_failed}

    @staticmethod
    def _build_query(camp) -> str:
        # Prefer specific address, fall back to admin region only.
        if camp.address:
            return camp.address
        sido = camp.region.sido or ""
        sigungu = camp.region.sigungu or ""
        joined = f"{sido} {sigungu}".strip()
        return joined
