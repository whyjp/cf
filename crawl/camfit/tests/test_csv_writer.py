from pathlib import Path

from camfit_crawl.csv_writer import CSV_FIELDS, read_rows, write_rows
from camfit_crawl.models import CampRecord


def test_write_then_read_roundtrip(tmp_path: Path):
    rows = [
        CampRecord(
            id="r1", name="A 캠프", region_sido="강원", region_sigungu="평창군",
            lat=37.5, lon=128.5,
            categories=["계곡", "키즈캠핑"], facilities=["트램펄린"],
            has_valley=True, has_kids=True, has_trampoline=True,
        ),
        CampRecord(id="r2", name="B 캠프"),
    ]
    out = tmp_path / "x.csv"
    n = write_rows(rows, out)
    assert n == 2

    # Header presence + BOM.
    text = out.read_text(encoding="utf-8-sig")
    first_line = text.splitlines()[0]
    for f in CSV_FIELDS:
        assert f in first_line

    back = read_rows(out)
    assert back[0].id == "r1"
    assert back[0].lat == 37.5
    assert back[0].has_valley is True
    assert back[0].categories == ["계곡", "키즈캠핑"]
    assert back[1].lat is None
