"""CSV writer — camfit-puller csv_writer 와 동형 + `source` 컬럼 (후속 통합 친화)."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from txcp_crawl.models import CampRecord


# CSV 헤더 = camfit-puller 와 통합 가능한 공통 컬럼 + txcp 보조.
# magic-number-traceability: 컬럼 순서는 페이즈 04 verification + plan u1 §6 기준.
HEADER = [
    "source",
    "id",
    "name",
    "sido",
    "sigungu",
    "address",
    "lat",
    "lon",
    "site_tp_codes",
    "thumbnail",
    "min_basic_price",
    "min_sale_price",
    "review_count",
    "monthly_review_count",
]


def _row(rec: CampRecord) -> list[str]:
    return [
        rec.source,
        rec.id,
        rec.name,
        rec.region_sido or "",
        rec.region_sigungu or "",
        rec.address or "",
        "" if rec.lat is None else f"{rec.lat:.6f}",
        "" if rec.lon is None else f"{rec.lon:.6f}",
        ",".join(rec.site_tp_codes),
        rec.thumbnail or "",
        "" if rec.min_basic_price is None else str(rec.min_basic_price),
        "" if rec.min_sale_price is None else str(rec.min_sale_price),
        "" if rec.review_count is None else str(rec.review_count),
        "" if rec.monthly_review_count is None else str(rec.monthly_review_count),
    ]


def write_camps_csv(path: Path, records: Iterable[CampRecord], *, append: bool = True) -> int:
    """Append records to CSV. 헤더는 파일이 비었을 때만 한 번."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = (not append) or (not path.exists()) or path.stat().st_size == 0
    mode = "a" if append else "w"
    n = 0
    with path.open(mode, encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        if write_header:
            w.writerow(HEADER)
        for rec in records:
            w.writerow(_row(rec))
            n += 1
    return n
