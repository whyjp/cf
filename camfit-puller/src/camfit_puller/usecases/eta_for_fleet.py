"""Use-case: compute drive ETA from a single origin to many camps.

Resolves each camp_id → place name (camp.address preferred, then sido+sigungu+name),
then batch-calls EtaProvider. Optional max_minutes filter marks 'within' camps.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from ..ports.repo import CampReader
from ..ports.eta import EtaProvider
from ..domain.models import EtaResult


@dataclass
class EtaForFleet:
    camp_reader: CampReader
    eta_provider: EtaProvider

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
        pairs: list[tuple[str, str]] = []
        place_for: dict[str, str] = {}
        for cid in camp_ids:
            camp = camps_by_id.get(cid)
            if not camp:
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
