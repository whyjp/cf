"""Convert data/camps_dedup.json (raw camfit shape) → data/camfit.csv (CampRecord)."""
from __future__ import annotations

import json
from pathlib import Path

from camfit_crawl.csv_writer import write_rows
from camfit_crawl.models import CampRecord
from camfit_crawl.parser import _classify_facilities


HERE = Path(__file__).resolve().parent.parent
SRC = HERE / "data" / "camps_dedup.json"
OUT = HERE / "data" / "camfit.csv"


def main() -> int:
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    print(f"[in] {SRC.name}: {len(raw)} camps")

    records: list[CampRecord] = []
    for r in raw:
        cid = r.get("id") or r.get("_id")
        if not cid:
            continue
        name = r.get("name") or "(이름 미상)"
        sido = r.get("city")
        sigungu = r.get("major")
        addr = " ".join(s for s in (sido, sigungu) if s) or None

        # Categories — combine inventory `type` + `_collections` (curation names) + representType.
        types = [t.strip() for t in (r.get("type") or "").split(",") if t.strip()]
        collections = list(r.get("_collections", []) or [])
        cats = sorted(set(types + collections))

        # Facilities/badges — placeholder until per-camp detail endpoint feeds the real list.
        facs: list[str] = []
        if r.get("isOnlinePaymentAvailable"): facs.append("온라인결제")
        if r.get("isCouponAvailable"):       facs.append("쿠폰")
        if r.get("isEasyCamping"):           facs.append("이지캠핑")
        if r.get("isSafeCancellation"):      facs.append("안전취소")

        # 4-axis flag derivation from category/collection text.
        merged = " ".join(cats + facs + [name, addr or ""])
        flags = _classify_facilities(merged)

        thumb = r.get("thumbnail")
        url = f"https://camfit.co.kr/camp/{cid}"

        records.append(
            CampRecord(
                id=str(cid),
                name=name,
                url=url,
                region_sido=sido,
                region_sigungu=sigungu,
                address=addr,
                lat=None,
                lon=None,
                categories=cats,
                facilities=facs,
                raw_image_url=thumb,
                **flags,
            )
        )

    n = write_rows(records, OUT)
    print(f"[out] {OUT.name}: {n} rows")
    print(f"[stats] valley: {sum(1 for r in records if r.has_valley)}")
    print(f"[stats] kids:   {sum(1 for r in records if r.has_kids)}")
    print(f"[stats] tramp:  {sum(1 for r in records if r.has_trampoline)}")
    print(f"[stats] sidos:  {sorted({r.region_sido for r in records if r.region_sido})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
