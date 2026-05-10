"""CSV writer — 콤마/따옴표/줄바꿈 escape (S4)."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tkcp_crawl.csv_writer import HEADER, write_camps_csv
from tkcp_crawl.models import CampRecord


@pytest.fixture
def tmp_csv(tmp_path: Path) -> Path:
    return tmp_path / "camps.csv"


def _record(**overrides) -> CampRecord:
    base = {"campSeq": "1", "campName": "x"}
    base.update(overrides)
    return CampRecord.model_validate(base)


def test_writes_header_on_first_call(tmp_csv: Path):
    n = write_camps_csv(tmp_csv, [_record()], append=True)
    assert n == 1
    rows = list(csv.reader(tmp_csv.open(encoding="utf-8")))
    assert rows[0] == HEADER
    assert len(rows) == 2


def test_does_not_double_header_on_append(tmp_csv: Path):
    write_camps_csv(tmp_csv, [_record(campSeq="1", campName="a")], append=True)
    write_camps_csv(tmp_csv, [_record(campSeq="2", campName="b")], append=True)
    rows = list(csv.reader(tmp_csv.open(encoding="utf-8")))
    assert rows[0] == HEADER
    assert len(rows) == 3  # 1 header + 2 data


def test_handles_comma_quote_newline_in_name(tmp_csv: Path):
    rec = _record(campSeq="9", campName='콤마,따옴표"줄바꿈\n포함')
    write_camps_csv(tmp_csv, [rec], append=True)
    with tmp_csv.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == HEADER
    assert rows[1][2] == '콤마,따옴표"줄바꿈\n포함'


def test_lat_lon_formatted_with_6_decimals(tmp_csv: Path):
    rec = _record(campSeq="1", campName="x", lat=37.123456789, lon=127.987654321)
    write_camps_csv(tmp_csv, [rec], append=True)
    rows = list(csv.reader(tmp_csv.open(encoding="utf-8")))
    assert rows[1][6] == "37.123457"
    assert rows[1][7] == "127.987654"


def test_overwrite_with_append_false_truncates(tmp_csv: Path):
    write_camps_csv(tmp_csv, [_record(campSeq="1", campName="a")], append=True)
    write_camps_csv(tmp_csv, [_record(campSeq="2", campName="b")], append=False)
    rows = list(csv.reader(tmp_csv.open(encoding="utf-8")))
    assert len(rows) == 2  # header + 1
    assert rows[1][1] == "2"
