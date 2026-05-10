"""Use-case: compute drive ETA from a single origin to many camps.

Resolves each camp_id → place name (camp.address preferred, then sido+sigungu+name),
then batch-calls EtaProvider. Optional max_minutes filter marks 'within' camps.

Pre-filter: when max_minutes is set and the origin can be geocoded, camps
outside the haversine radius (max_minutes/60 × 90 km/h × 1.3 detour factor)
are skipped without a driving-ETA call. Cuts the batch from 1,656 camps to
~300-600 in typical Seoul-out queries.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional

from ..ports.repo import CampReader
from ..ports.eta import EtaProvider
from ..ports.geocode import Geocoder
from ..domain.models import EtaResult


# Korean expressway-skewed avg + detour safety factor. 90×1.3 = 117 km per
# road-hour. A 2-hour budget → 234 km haversine radius from the origin.
_AVG_KMH = 90.0
_DETOUR_FACTOR = 1.3


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


@dataclass
class EtaForFleet:
    camp_reader: CampReader
    eta_provider: EtaProvider
    geocoder: Optional[Geocoder] = None

    def execute(
        self,
        origin: str,
        camp_ids: list[str],
        *,
        max_minutes: Optional[int] = None,
        concurrency: int = 4,
        timeout_s: float = 12.0,
    ) -> dict:
        camps_by_id = {c.id: c for c in self.camp_reader.list_filtered(ids=camp_ids)}

        # Haversine pre-filter — skip camps obviously beyond the time budget
        # before paying for a driving-ETA call. Active only when both
        # max_minutes and an origin geocode are available, AND the camp has
        # coordinates. Camps without geo fall through to the road-ETA path.
        radius_km = None
        origin_geo = None
        if max_minutes and self.geocoder is not None:
            try:
                origin_geo = self.geocoder.lookup(origin)
            except Exception:
                origin_geo = None
            if origin_geo is not None:
                radius_km = (max_minutes / 60.0) * _AVG_KMH * _DETOUR_FACTOR

        pairs: list[tuple[str, str]] = []
        place_for: dict[str, str] = {}
        prefiltered: dict[str, float] = {}  # camp_id → haversine km (skipped from road call)
        for cid in camp_ids:
            camp = camps_by_id.get(cid)
            if not camp:
                continue
            if radius_km is not None and origin_geo is not None and camp.geo is not None:
                d = _haversine_km(origin_geo.lat, origin_geo.lon, camp.geo.lat, camp.geo.lon)
                if d > radius_km:
                    prefiltered[cid] = d
                    continue
            place = self._place_for(camp)
            if not place:
                continue
            pairs.append((cid, place))
            place_for[cid] = place

        raw: dict[str, EtaResult] = self.eta_provider.drive_eta_batch(
            origin, pairs, concurrency=concurrency, timeout_s=timeout_s,
        )

        results = []
        within = 0
        for cid in camp_ids:
            if cid in prefiltered:
                results.append({
                    "id": cid,
                    "minutes": None,
                    "source": "prefilter",
                    "error": f"~{prefiltered[cid]:.0f}km > {radius_km:.0f}km radius",
                    "within": False,
                    "place": None,
                })
                continue
            if cid not in raw:
                results.append({
                    "id": cid, "minutes": None, "source": None,
                    "error": "no place name", "within": False, "place": None,
                })
                continue
            r = raw[cid]
            ok = r.minutes is not None and (
                max_minutes is None or r.minutes <= max_minutes
            )
            if ok:
                within += 1
            results.append({
                "id": cid,
                "minutes": r.minutes,
                "source": r.source,
                "error": r.error,
                "within": ok,
                "place": place_for.get(cid),
            })
        return {
            "origin": origin,
            "max_minutes": max_minutes,
            "checked": len(results),
            "within_count": within,
            "prefiltered": len(prefiltered),
            "radius_km": round(radius_km, 1) if radius_km else None,
            "results": results,
        }

    @staticmethod
    def _place_for(camp) -> str:
        sido = (camp.region.sido or "").strip()
        sigungu = (camp.region.sigungu or "").strip()
        region = " ".join(filter(None, [sido, sigungu])).strip()
        if region and region != "(미지정) (미지정)" and "(미지정)" not in region:
            return region
        if camp.address:
            return camp.address.strip()
        if camp.name:
            return camp.name.strip()
        return camp.id
