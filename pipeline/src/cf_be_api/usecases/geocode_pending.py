"""Use-case: geocode all camps that don't yet have lat/lon.

Reads camps where `camp.geo is None`, calls the Geocoder for each, persists via
CampWriter.set_geo(...). Idempotent — re-runs only those still missing geo.

Address-first policy (spec §5): we use camp.address (or fall back to
'sido sigungu' as a coarser hint) as the geocode query. NO coord fallback —
if the geocoder fails, the camp simply remains without coords.

Batch path: when the wired Geocoder exposes ``lookup_many``, all pending
addresses are resolved in a single shot — for the etago adapter that means
ONE subprocess fans out to N parallel HTTP requests inside Go, instead of
one Python subprocess per camp. This is essential at the 1.6k-camp scale
where Naver/Kakao have no native batch endpoints but spawn cost dominates
without it.

Per-item path is kept for backward compatibility with Geocoders that lack
``lookup_many`` (e.g. NominatimGeocoder). It uses a ThreadPoolExecutor with
``workers`` lanes; cache hits parallelize cleanly while Nominatim's 1.05s
rate-limit lock continues to honor the OSM ToS.
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
        if not pending:
            return {"attempted": 0, "resolved": 0, "failed": 0}

        # Prefer the batch path when available. The CachedGeocoder wrapper
        # forwards lookup_many to its inner provider, so the etago subprocess
        # adapter gets to fan out under one process spawn.
        if hasattr(self.geocoder, "lookup_many"):
            return self._execute_batch(pending)
        return self._execute_per_item(pending, workers=workers)

    # ─────────────────────────── batch path ───────────────────────────

    def _execute_batch(self, pending) -> dict:
        # Group camps by their geocode query. Duplicate addresses (e.g.
        # "1캠핑장" / "2캠핑장" at the same lot) collapse to one upstream
        # call but write coords to each camp.
        no_query = 0
        camp_by_addr: dict[str, list] = {}
        hint_by_addr: dict[str, str | None] = {}
        for camp in pending:
            q = self._build_query(camp)
            if not q:
                no_query += 1
                continue
            camp_by_addr.setdefault(q, []).append(camp)
            # First non-empty hint wins; later camps don't overwrite.
            if hint_by_addr.get(q) is None and camp.name:
                hint_by_addr[q] = camp.name

        if not camp_by_addr:
            return {"attempted": 0, "resolved": 0, "failed": no_query}

        items = [(addr, hint_by_addr.get(addr)) for addr in camp_by_addr.keys()]

        resolved_map = self.geocoder.lookup_many(items)

        n_resolved = 0
        n_failed = 0
        # Multiple camps can legitimately share the same address (e.g.
        # 1캠핑장 / 2캠핑장 at the same lot). We persist the same coord to
        # each of them.
        for addr, camps in camp_by_addr.items():
            point = resolved_map.get(addr)
            if point is None:
                n_failed += len(camps)
                continue
            for camp in camps:
                self.camp_writer.set_geo(camp.id, point.lat, point.lon)
                n_resolved += 1
        return {
            "attempted": len(pending),
            "resolved": n_resolved,
            "failed": n_failed + no_query,
        }

    # ───────────────────────── per-item path ──────────────────────────

    def _execute_per_item(self, pending, *, workers: int = 1) -> dict:
        n_attempted = 0
        n_resolved = 0
        n_failed = 0
        workers = max(1, min(workers, 4))  # respect Nominatim ~1rps
        lock = Lock()

        def _process(camp) -> str:
            query = self._build_query(camp)
            if not query:
                return "failed"
            point = self.geocoder.lookup(query, hint=camp.name or None)
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
