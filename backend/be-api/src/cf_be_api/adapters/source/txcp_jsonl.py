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

# camping site_tp codes — records lacking ALL of these and having BB003 (pension)
# are filtered out at iter_summaries. See user directive 2026-05-10:
# "캠핑장이외의 펜션데이터는 파이프라인 처리하지않는다".
_CAMPING_SITE_TPS = frozenset({"BB000", "BB001", "BB002", "BB006"})


def _is_pension_only(raw: dict) -> bool:
    """True if this record is BB003 (펜션) and has no camping code.

    KEEP if: any camping code present, OR site_tp empty/unknown (안전).
    DROP if: BB003 in codes AND no camping code.
    """
    codes = set(raw.get("site_tp_codes") or [])
    return "BB003" in codes and not (codes & _CAMPING_SITE_TPS)


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
            if _is_pension_only(raw):
                # 펜션 only -- pipeline 처리 제외 (사용자 directive 2026-05-10)
                continue
            yield self._to_camp(raw)

    def get_detail(self, camp_id: str) -> Optional[Camp]:
        """Return enriched Camp from data/details/{cseq}.json if available, else summary.

        camp_id may arrive with or without "txcp:" prefix. The summary acts as
        the fallback baseline; any keys present in the detail JSON augment / replace
        the summary fields:
          - photos: prepend detail photos (host-relative URLs absolutized)
          - description / brief: from label_value_pairs if a known label maps
          - hashtags / facilities: empty until a richer parser ships
        """
        key = camp_id[5:] if camp_id.startswith("txcp:") else camp_id
        raw = self._records.get(str(key))
        if raw is None:
            return None
        camp = self._to_camp(raw)
        return self._enrich_with_detail(camp, str(key))

    def iter_reviews(self, camp_id: str, *, sort: str = "recommend") -> Iterator[Review]:
        # Reviews require richer detail-page parsing (review section). The
        # current minimal parser does not surface them yet; the raw HTML in
        # data/details_html/{cseq}.html is preserved for a future parser pass.
        return iter([])

    def iter_filters(self) -> Iterator[tuple[str, str, str, dict | None]]:
        # txcp categorisation = the 5 site_tp codes; surface as kind="site_tp".
        for code, label in _SITE_TP_LABEL.items():
            yield code, label, "site_tp", {"site_tp_code": code}

    # ─────────────────────────────────────── private

    def _enrich_with_detail(self, summary: Camp, cseq: str) -> Camp:
        """If data/details/{cseq}.json exists, merge its fields into summary."""
        det_path = self._dir / "details" / f"{cseq}.json"
        if not det_path.exists():
            return summary
        try:
            det = json.loads(det_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return summary

        # Photos: prepend the (typically richer) detail photos. Absolutize host-relative.
        merged_photos = list(summary.photos)
        seen_urls = {p.url for p in merged_photos}
        for src in det.get("photos") or []:
            url = src if src.startswith("http") else f"https://image.thankqcamping.com{src}"
            if url in seen_urls:
                continue
            seen_urls.add(url)
            merged_photos.append(Photo(url=url))

        # Label-value pairs to known fields. Empty `pairs` is fine.
        pairs: dict[str, str] = det.get("label_value_pairs") or {}
        # Heuristic mapping for the 4 commonly-seen labels (probed): 예약 / 주소 / 전화 / Q-Point.
        # We surface 주소 if it adds info, contact if not already set, and 예약 description as brief.
        new_address = pairs.get("주소") or summary.address
        new_contact = pairs.get("전화") or summary.contact
        new_brief = pairs.get("예약") or summary.brief

        return summary.model_copy(update={
            "photos": merged_photos,
            "address": new_address,
            "contact": new_contact,
            "brief": new_brief,
        })

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
