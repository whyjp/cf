"""CSV writer — UTF-8 BOM, semicolon-joined multi-value lists, stable schema."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .models import CampRecord

CSV_FIELDS = (
    "id",
    "name",
    "url",
    "region_sido",
    "region_sigungu",
    "address",
    "lat",
    "lon",
    "categories",
    "facilities",
    "has_valley",
    "has_kids",
    "has_trampoline",
    "raw_image_url",
    "description",
)


def _row(rec: CampRecord) -> dict[str, str]:
    d = rec.model_dump()
    return {
        k: (";".join(d.get(k) or []) if isinstance(d.get(k), list)
            else ("" if d.get(k) is None else str(d.get(k))))
        for k in CSV_FIELDS
    }


def write_rows(records: Iterable[CampRecord], out_path: str | Path) -> int:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(CSV_FIELDS))
        w.writeheader()
        for rec in records:
            w.writerow(_row(rec))
            n += 1
    return n


def read_rows(in_path: str | Path) -> list[CampRecord]:
    out: list[CampRecord] = []
    with Path(in_path).open("r", encoding="utf-8-sig", newline="") as fp:
        for row in csv.DictReader(fp):
            payload = dict(row)
            for k in ("categories", "facilities"):
                payload[k] = [s for s in (payload.get(k) or "").split(";") if s]
            for k in ("lat", "lon"):
                v = payload.get(k)
                payload[k] = float(v) if v else None
            for k in ("has_valley", "has_kids", "has_trampoline"):
                v = (payload.get(k) or "").lower()
                payload[k] = True if v == "true" else False if v == "false" else None
            out.append(CampRecord(**{k: v for k, v in payload.items() if v != ""}))
    return out
