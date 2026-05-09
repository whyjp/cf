"""Use-case: geocode all camps that don't yet have lat/lon.

Reads camps where `camp.geo is None`, calls the Geocoder for each, persists via
CampWriter.set_geo(...). Idempotent — re-runs only those still missing geo.

Address-first policy (spec §5): we use camp.address (or fall back to
'sido sigungu' as a coarser hint) as the geocode query. NO coord fallback —
if the geocoder fails, the camp simply remains without coords.

Parallelism: when `workers > 1` is passed to `execute()`, lookups run on a
ThreadPoolExecutor.  Cache hits (PG geocode_cache) parallelize cleanly; cache
misses still serialize through NominatimGeocoder's internal 1.05s rate-limit
lock, which is the correct behavior to honor the Nominatim ToS.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Lock

from ..ports.repo import CampReader, CampWriter
from ..ports.geocode import Geocoder


@dataclass
class GeocodePending:
    camp_reader: CampReader
    camp_writer: CampWriter
    geocoder: Geocoder

    def execute(self, *, workers: int = 1) -> dict:
        # Materialize the pending set up front so we can fan out cleanly.
        pending = [c for c in self.camp_reader.iter_all() if c.geo is None]
        n_attempted = 0
        n_resolved = 0
        n_failed = 0
        if not pending:
            return {"attempted": 0, "resolved": 0, "failed": 0}

        workers = max(1, min(workers, 4))  # respect Nominatim ~1rps; 4 is plenty for cache hits

        # Counters guarded for the parallel path; in serial it's a no-op cost.
        lock = Lock()

        def _process(camp) -> str:
            """Returns 'resolved' | 'failed' | 'no_query'."""
            query = self._build_query(camp)
            if not query:
                return "failed"
            point = self.geocoder.lookup(query)
            if point is None:
                return "failed"
            self.camp_writer.set_geo(camp.id, point.lat, point.lon)
            return "resolved"

        if workers == 1:
            for camp in pending:
                n_attempted += 1
                r = _process(camp)
                if r == "resolved":
                    n_resolved += 1
                else:
                    n_failed += 1
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = {pool.submit(_process, c): c for c in pending}
                for f in as_completed(futs):
                    with lock:
                        n_attempted += 1
                    r = f.result()
                    with lock:
                        if r == "resolved":
                            n_resolved += 1
                        else:
                            n_failed += 1

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
