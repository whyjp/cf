"""Predicate `is_camping_facility` — covers source-mixed + edge cases.

User directive 2026-05-10: "땡큐의 캠핑장외 데이터는 로드하지 않는다."
The predicate is the policy enforcement point — keep these tests in sync with
`cf_be_api.domain.camping_filter.CAMPING_TOKENS`.
"""
from __future__ import annotations
import pytest

from cf_be_api.domain.camping_filter import is_camping_facility, CAMPING_TOKENS
from cf_be_api.domain.models import Camp, Region


def _camp(**kw) -> Camp:
    """Mint a minimal Camp with the given override fields."""
    base = dict(
        id=kw.pop("id", "x"),
        name=kw.pop("name", "x"),
        region=Region(sido="강원", sigungu="평창군"),
    )
    base.update(kw)
    return Camp(**base)


# ───────────────────────── txcp BB-codes (only) ────────────────────────

def test_bb000_only_is_camping():
    """txcp 오토캠핑 — must INCLUDE."""
    assert is_camping_facility(_camp(types=["BB000"]))


def test_bb003_only_is_not_camping():
    """txcp 펜션 only — must EXCLUDE."""
    assert not is_camping_facility(_camp(types=["BB003"]))


def test_bb000_plus_bb003_is_camping():
    """오토캠핑+펜션 combo — at least one camping token wins → INCLUDE."""
    assert is_camping_facility(_camp(types=["BB000", "BB003"]))


def test_bb008_only_is_not_camping():
    """BB008 (미지정) — conservative DROP since semantics unclear."""
    assert not is_camping_facility(_camp(types=["BB008"]))


def test_bb999_alone_is_not_camping():
    """BB999 (미분류) by itself is not camping (per spec safe rule)."""
    assert not is_camping_facility(_camp(types=["BB999"]))


def test_bb999_plus_bb000_is_camping():
    """BB999+오토캠핑 combo — keep."""
    assert is_camping_facility(_camp(types=["BB999", "BB000"]))


# ───────────────────────── camfit English codes ────────────────────────

def test_camfit_pension_only_is_not_camping():
    """camfit `pension` only — DROP (rental cabin, not camping)."""
    assert not is_camping_facility(_camp(types=["pension"]))


def test_camfit_bungalow_only_is_not_camping():
    """camfit `bungalow` only — DROP (rental cabin)."""
    assert not is_camping_facility(_camp(types=["bungalow"]))


def test_camfit_rental_only_is_not_camping():
    """camfit `rental` only — DROP."""
    assert not is_camping_facility(_camp(types=["rental"]))


def test_camfit_autocamping_is_camping():
    assert is_camping_facility(_camp(types=["autoCamping"]))


def test_camfit_glamping_is_camping():
    assert is_camping_facility(_camp(types=["glamping"]))


def test_camfit_caravan_is_camping():
    assert is_camping_facility(_camp(types=["caravan"]))


def test_camfit_carCamping_is_camping():
    assert is_camping_facility(_camp(types=["carCamping"]))


def test_camfit_trailer_is_camping():
    assert is_camping_facility(_camp(types=["trailer"]))


def test_camfit_experience_is_camping():
    assert is_camping_facility(_camp(types=["experience"]))


def test_camfit_pension_plus_autocamping_is_camping():
    """pension+autoCamping — combo INCLUDE."""
    assert is_camping_facility(_camp(types=["pension", "autoCamping"]))


# ───────────────────────── txcp Korean labels ──────────────────────────

def test_korean_pension_only_is_not_camping():
    assert not is_camping_facility(_camp(types=["펜션"]))


def test_korean_autocamping_only_is_camping():
    assert is_camping_facility(_camp(types=["오토캠핑"]))


def test_korean_glamping_only_is_camping():
    assert is_camping_facility(_camp(types=["글램핑"]))


def test_korean_picnic_only_is_camping():
    """피크닉 — txcp BB006."""
    assert is_camping_facility(_camp(types=["피크닉"]))


def test_korean_pension_plus_glamping_is_camping():
    assert is_camping_facility(_camp(types=["펜션", "글램핑", "오토캠핑"]))


# ───────────────────────── empty / unknown ─────────────────────────────

def test_no_types_is_not_camping():
    """Empty types AND empty location_types — DROP (safe)."""
    assert not is_camping_facility(_camp(types=[], location_types=[]))


def test_unknown_token_is_not_camping():
    """Random unknown string — DROP."""
    assert not is_camping_facility(_camp(types=["BB012", "zzz"]))


# ───────────────────────── dict input shape ────────────────────────────

def test_accepts_dict_shape():
    """Predicate accepts Camp.model_dump() dict — used by BFF/test fixtures."""
    assert is_camping_facility({"types": ["autoCamping"], "location_types": []})
    assert not is_camping_facility({"types": ["pension"], "location_types": []})
    assert not is_camping_facility({})


def test_dict_with_only_location_types_falls_through():
    """location_types tokens are scanned too — but none of the standard
    LocationType names (mountain/forest/...) are camping markers, so a record
    with ONLY a `mountain` location_type is still excluded if its types list
    has no camping token. This protects against the inverse false-positive."""
    assert not is_camping_facility(
        {"types": ["pension"], "location_types": ["mountain", "forest"]}
    )


# ───────────────────────── token-set sanity ────────────────────────────

def test_camping_tokens_contains_known_codes():
    """Lock in the contract — these MUST stay camping. Editing the set should
    require touching this assertion (forces a deliberate vocabulary change)."""
    expected_camping = {
        "autoCamping", "glamping", "caravan", "carCamping", "trailer", "experience",
        "오토캠핑", "글램핑", "카라반", "피크닉", "차박", "체험", "트레일러",
        "BB000", "BB001", "BB002", "BB006",
    }
    assert CAMPING_TOKENS == expected_camping


def test_camping_tokens_excludes_pension_codes():
    """Pension/lodging tokens must NOT be in the camping set."""
    for tok in ("pension", "bungalow", "rental", "펜션", "방갈로", "렌탈",
                "BB003", "BB008", "BB999"):
        assert tok not in CAMPING_TOKENS, f"{tok!r} must NOT be a camping token"
