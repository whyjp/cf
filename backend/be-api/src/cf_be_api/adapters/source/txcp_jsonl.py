"""txcp DataSource — reads jsonl file from crawl/txcp/data/.

Reads:
  - data/camps.jsonl  (each line = one txcp_crawl CampRecord JSON)

Camp.id is namespaced "txcp:{campSeq}" so it never collides with camfit ids
(camfit ids are alphanumeric strings; txcp ids are numeric campSeq).

detail_url uses list API's campSeq directly as the view URL's cseq parameter:
  /resv/view.hbb?cseq={campSeq}
This was verified by probing real campSeqs (16706, 17644, 4254) — each returned
200 OK with the matching campseq embedded in the page JS, confirming the
identity. No mapping bridge needed.

iter_reviews + detail-page text fields (description / hashtags / etc.) require
fetching the 130KB+ per-camp HTML and parsing it. That richer crawl lands in a
separate sprint; this adapter currently surfaces only the list-API summary.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import quote

from ...domain.models import Camp, GeoPoint, Photo, Region, Review


# magic-number-traceability: site-tp -> Korean label, used in placeholder
# detail_url query string. Mirrors txcp_crawl probes/FINDINGS.md §1.
_SITE_TP_LABEL = {
    "BB000": "오토캠핑",
    "BB001": "글램핑",
    "BB002": "카라반",
    "BB003": "펜션",
    "BB006": "피크닉",
}


class TxcpJsonlSource:
    """DataSource adapter for txcp camps.jsonl.

    Each jsonl line is a `txcp_crawl.models.CampRecord.model_dump_json()` output
    with these populated fields: id (campSeq str), name, region_sido,
    region_sigungu, address, lat, lon, site_tp_codes, thumbnail,
    min_basic_price, min_sale_price, review_count, monthly_review_count,
    source ("thankqcamping"), pulled_at.
    """

    name = "txcp-jsonl"

    def __init__(self, data_dir: Path):
        self._dir = Path(data_dir)
        self._records = self._load()

    def _load(self) -> dict[str, dict]:
        p = self._dir / "camps.jsonl"
        if not p.exists():
            return {}
        result: dict[str, dict] = {}
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rid = raw.get("id")
                if not rid:
                    continue
                result[str(rid)] = raw
        return result

    def iter_summaries(self) -> Iterator[Camp]:
        for raw in self._records.values():
            yield self._to_camp(raw)

    def get_detail(self, camp_id: str) -> Optional[Camp]:
        # detail-bridge not yet implemented: fall back to summary.
        # camp_id may arrive with or without "txcp:" prefix.
        key = camp_id[5:] if camp_id.startswith("txcp:") else camp_id
        raw = self._records.get(str(key))
        return self._to_camp(raw) if raw else None

    def iter_reviews(self, camp_id: str, *, sort: str = "recommend") -> Iterator[Review]:
        # Reviews require detail-bridge crawl (per-camp HTML page parse). Empty
        # until that sprint lands.
        return iter([])

    def iter_filters(self) -> Iterator[tuple[str, str, str, dict | None]]:
        # txcp categorisation = the 5 site_tp codes; surface as kind="site_tp".
        for code, label in _SITE_TP_LABEL.items():
            yield code, label, "site_tp", {"site_tp_code": code}

    # ─────────────────────────────────────── private

    def _to_camp(self, raw: dict) -> Camp:
        rid = str(raw["id"])
        namespaced_id = f"txcp:{rid}"

        # campPicList in raw upstream JSON is preserved in CampRecord via
        # extra="allow", but our CampRecord projects only `thumbnail`. Use that
        # as the single Photo for now; detail crawl adds full set.
        photos: list[Photo] = []
        thumb = raw.get("thumbnail")
        if thumb:
            photos.append(Photo(url=thumb))

        # Coords arrive as None from list API. Geocode pipeline fills them later.
        geo: Optional[GeoPoint] = None
        if raw.get("lat") is not None and raw.get("lon") is not None:
            try:
                geo = GeoPoint(lat=float(raw["lat"]), lon=float(raw["lon"]))
            except Exception:
                geo = None

        # detail_url — list API's campSeq IS the view URL's cseq (verified
        # 2026-05-10 via probe: cseq=campSeq returns 200 OK + matching campseq
        # in JS body). Direct use, no mapping bridge needed.
        detail_url = f"https://m.thankqcamping.com/resv/view.hbb?cseq={rid}"

        # types from site_tp codes
        types = [
            _SITE_TP_LABEL.get(c, c)
            for c in (raw.get("site_tp_codes") or [])
        ]

        return Camp(
            id=namespaced_id,
            name=raw.get("name") or "(이름 미상)",
            region=Region(
                sido=raw.get("region_sido") or "(미지정)",
                sigungu=raw.get("region_sigungu") or "(미지정)",
            ),
            address=raw.get("address"),
            geo=geo,
            types=types,
            facilities=[],          # populated by detail-bridge
            additional_facilities=[],
            location_types=[],
            hashtags=[],
            collections=[],
            description=None,        # detail-bridge fills
            brief=None,
            location_brief=None,
            contact=None,
            price_start_from=raw.get("min_basic_price"),
            price_end_to=raw.get("min_sale_price"),
            num_of_reviews=int(raw.get("review_count") or 0),
            num_of_viewed=0,         # txcp does not expose
            bookmark_count=0,
            url=f"https://m.thankqcamping.com/resv/list.hbb?keyword={quote(raw.get('name') or '')}",
            source="txcp",
            detail_url=detail_url,
            photos=photos,
        )
