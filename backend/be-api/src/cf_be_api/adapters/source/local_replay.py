"""Local replay DataSource — reads pre-fetched camfit JSON files from data/.

Reads:
  - data/camps_dedup.json  (summary list, source of all known camp ids)
  - data/details/<id>.json (detail per camp, optional)
  - data/reviews/<id>.json (top-N reviews per camp, optional)

iter_filters() returns empty for local-replay — camfit-native taxonomy is fetched
live (CamfitCloakSource) or seeded manually (seed_filter_mapping.py).
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Iterator, Optional

from ...domain.models import Camp, GeoPoint, Photo, Region, Review


class LocalReplaySource:
    name = "local-replay"

    def __init__(self, data_dir: Path):
        self._dir = Path(data_dir)
        self._dedup = self._load_dedup()

    def _load_dedup(self) -> dict[str, dict]:
        p = self._dir / "camps_dedup.json"
        if not p.exists():
            return {}
        result: dict[str, dict] = {}
        for c in json.loads(p.read_text(encoding="utf-8")):
            cid = c.get("id") or c.get("_id")
            if not cid:
                continue
            # normalise so downstream code always sees "id"
            if "id" not in c or not c["id"]:
                c = dict(c, id=cid)
            result[cid] = c
        return result

    def iter_summaries(self) -> Iterator[Camp]:
        for cid, raw in self._dedup.items():
            yield self._summary(raw)

    def get_detail(self, camp_id: str) -> Optional[Camp]:
        d = self._dir / "details" / f"{camp_id}.json"
        if d.exists():
            try:
                raw = json.loads(d.read_text(encoding="utf-8"))
                return self._detail(raw, fallback=self._dedup.get(camp_id, {}))
            except Exception:
                pass
        # Fall back to summary if detail missing
        if camp_id in self._dedup:
            return self._summary(self._dedup[camp_id])
        return None

    def iter_reviews(self, camp_id: str, *, sort: str = "recommend") -> Iterator[Review]:
        rp = self._dir / "reviews" / f"{camp_id}.json"
        if not rp.exists():
            return
        try:
            rj = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:
            return
        for rv in rj.get("reviews", []):
            try:
                yield Review(
                    id=rv["id"],
                    camp_id=camp_id,
                    user_nick=(rv.get("user") or {}).get("nickname"),
                    season=rv.get("season"),
                    user_type=rv.get("userType"),
                    num_of_days=rv.get("numOfDays"),
                    score=float(rv["totalScore"]) if rv.get("totalScore") is not None else None,
                    text=rv.get("text") or "",
                    is_clean=rv.get("isClean"),
                    is_kind=rv.get("isKind"),
                    is_manner=rv.get("isMannerTimeMaintained"),
                    is_convenient=rv.get("isConvenient"),
                    review_timestamp=rv.get("reviewTimestamp"),
                    medias=[m["url"] for m in (rv.get("medias") or []) if m.get("url")],
                )
            except Exception:
                continue

    def iter_filters(self) -> Iterator[tuple[str, str, str, dict | None]]:
        # local-replay does not surface camfit's native taxonomy.
        return iter([])

    def _summary(self, raw: dict) -> Camp:
        return Camp(
            id=raw["id"],
            name=raw.get("name") or "(이름 미상)",
            region=Region(
                sido=raw.get("city") or "(미지정)",
                sigungu=raw.get("major") or "(미지정)",
            ),
            url=raw.get("url") or f"https://camfit.co.kr/camp/{raw['id']}",
            types=[t.strip() for t in (raw.get("type") or "").split(",") if t.strip()],
            collections=raw.get("_collections") or [],
        )

    def _detail(self, raw: dict, fallback: dict) -> Camp:
        photos = []
        for m in (raw.get("medias") or [])[:8]:
            f = m.get("formats") or {}
            small = f.get("small") if isinstance(f, dict) else None
            photos.append(Photo(
                url=m.get("url"),
                thumb_url=(small or {}).get("url") if isinstance(small, dict) else None,
                width=m.get("width"),
                height=m.get("height"),
            ))
        return Camp(
            id=raw["id"],
            name=raw.get("name") or fallback.get("name") or "(이름 미상)",
            region=Region(
                sido=raw.get("city") or "(미지정)",
                sigungu=raw.get("major") or "(미지정)",
            ),
            address=" ".join(filter(None, [raw.get("address1"), raw.get("address2")])) or None,
            description=raw.get("description"),
            brief=raw.get("brief"),
            location_brief=raw.get("locationBrief"),
            contact=raw.get("contact"),
            price_start_from=raw.get("priceStartFrom"),
            price_end_to=raw.get("priceEndTo"),
            num_of_reviews=int(raw.get("numOfReviews") or 0),
            num_of_viewed=int(raw.get("numOfViewed") or 0),
            bookmark_count=int(raw.get("bookmarkCount") or 0),
            url=f"https://camfit.co.kr/camp/{raw['id']}",
            types=list(raw.get("types") or []),
            facilities=list(raw.get("facilities") or []),
            additional_facilities=list(raw.get("additionalFacilities") or []),
            location_types=list(raw.get("locationTypes") or []),
            hashtags=list(raw.get("hashtags") or []),
            collections=list(fallback.get("_collections") or []),
            photos=photos,
        )
