"""Dedup — (source, id) PK 단일 record (I-3)."""
from __future__ import annotations

from tkcp_crawl.models import CampRecord


def test_dedup_collapses_duplicate_campseq():
    a = CampRecord.model_validate({"campSeq": "1", "campName": "first"})
    b = CampRecord.model_validate({"campSeq": "1", "campName": "second-pull"})
    seen: set[tuple[str, str]] = set()
    persisted: list[CampRecord] = []
    for rec in [a, b]:
        if rec.dedup_key() in seen:
            continue
        seen.add(rec.dedup_key())
        persisted.append(rec)
    assert len(persisted) == 1
    assert persisted[0].name == "first"


def test_different_campseq_kept_separate():
    a = CampRecord.model_validate({"campSeq": "1", "campName": "x"})
    b = CampRecord.model_validate({"campSeq": "2", "campName": "y"})
    assert a.dedup_key() != b.dedup_key()


def test_source_distinguishes_same_id():
    """후속 entity-resolution 친화: 다른 source 의 동일 id 가 충돌하지 않는다."""
    a = CampRecord.model_validate({"campSeq": "1", "campName": "x"})
    b = CampRecord.model_validate({"campSeq": "1", "campName": "x", "source": "camfit"})
    assert a.dedup_key() != b.dedup_key()
