"""CampRecord 단위 테스트 — alias / extra=allow / KR 좌표 가드 / dedup PK."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from txcp_crawl.models import CampRecord


def test_alias_choices_campSeq_to_id():
    rec = CampRecord.model_validate({"campSeq": 1234, "campName": "테스트"})
    assert rec.id == "1234"
    assert rec.name == "테스트"


def test_alias_choices_addr_to_address():
    rec = CampRecord.model_validate({"campSeq": "1", "campName": "x", "addr": "서울 강남구"})
    assert rec.address == "서울 강남구"


def test_extra_allow_preserves_unknown_fields():
    rec = CampRecord.model_validate({
        "campSeq": "1",
        "campName": "x",
        "futureNewField": "value",
    })
    dumped = rec.model_dump()
    assert dumped.get("futureNewField") == "value"


def test_kr_coord_out_of_range_becomes_none():
    rec = CampRecord.model_validate({"campSeq": "1", "campName": "x", "lat": 10.0, "lon": 200.0})
    assert rec.lat is None
    assert rec.lon is None


def test_kr_coord_in_range_preserved():
    rec = CampRecord.model_validate({"campSeq": "1", "campName": "x", "lat": 37.5, "lon": 127.0})
    assert rec.lat == 37.5
    assert rec.lon == 127.0


def test_dedup_key_is_source_id_pair():
    rec = CampRecord.model_validate({"campSeq": "42", "campName": "x"})
    assert rec.dedup_key() == ("thankqcamping", "42")


def test_site_tps_csv_to_list():
    rec = CampRecord.model_validate({"campSeq": "1", "campName": "x", "siteTps": "BB000,BB001 ,BB002"})
    assert rec.site_tp_codes == ["BB000", "BB001", "BB002"]


def test_required_fields_missing_raises():
    with pytest.raises(ValidationError):
        CampRecord.model_validate({"campName": "x"})  # no campSeq/id
    with pytest.raises(ValidationError):
        CampRecord.model_validate({"campSeq": "1"})  # no campName/name
