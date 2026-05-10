"""Predicate: is this camp a *camping* facility (vs. pure pension/lodging)?

User directive 2026-05-10: "땡큐의 캠핑장외 데이터는 로드하지 않는다."
We extend the same intent to *all* sources at the read API: a camp is surfaced
in /sites only if at least one of its type/category/location-type tokens is a
recognised CAMPING token. Pure pension / bungalow / unknown-only records are
dropped — even if they survived ingest.

Token vocabulary
----------------
camfit `Camp.types` carries English codes (autoCamping, pension, glamping,
caravan, bungalow, rental, carCamping, experience, trailer).

txcp `Camp.types` carries Korean labels (오토캠핑, 펜션, 글램핑, 카라반, 피크닉,
체험) AND occasionally raw txcp BB### codes for unknown taxonomy entries
(BB008/BB999/BB012/...).

Rule
----
INCLUDE if `types` (and `location_types`) contains ANY token in
`CAMPING_TOKENS`.

EXCLUDE otherwise — covers:
  - pension-only (pension / 펜션 / BB003)
  - bungalow / rental / 방갈로 / 렌탈
  - unknown-only (BB008 / BB999 / BB012 / ...)
  - empty types

Combos are kept by construction: a record with [pension, autoCamping] still
has a camping token and is INCLUDED. An 오토캠핑+BB999 record is also kept.

Why a separate predicate (vs. SQL filter): keeps the rule in the domain layer,
testable in isolation, and trivially reusable from BFF/CLI/tests. The
performance hit is one set membership check per camp — negligible vs. PG round-
trips.
"""
from __future__ import annotations
from typing import Any, Iterable

# Tokens that mark a camp as a *camping* facility. Mix of camfit English codes,
# txcp Korean labels, and raw txcp BB### codes so the predicate works on any
# `Camp.model_dump()` regardless of source.
CAMPING_TOKENS: frozenset[str] = frozenset({
    # camfit English codes
    "autoCamping", "glamping", "caravan", "carCamping", "trailer", "experience",
    # txcp Korean labels (the ingest already maps known BB### → Korean)
    "오토캠핑", "글램핑", "카라반", "피크닉", "차박", "체험", "트레일러",
    # raw txcp BB### codes (defensive — only the explicitly-camping ones)
    "BB000", "BB001", "BB002", "BB006",
})


def _tokens_for(camp: Any) -> Iterable[str]:
    """Yield every type/location_type token from a Camp model OR a dict."""
    if hasattr(camp, "types") and hasattr(camp, "location_types"):
        # Pydantic Camp model
        yield from (camp.types or [])
        yield from (camp.location_types or [])
        return
    # Plain dict shape (Camp.model_dump())
    yield from (camp.get("types") or [])
    yield from (camp.get("location_types") or [])


def is_camping_facility(camp: Any) -> bool:
    """True iff the camp has at least one recognised camping token.

    Accepts either a `cf_be_api.domain.models.Camp` instance or a dict in the
    `Camp.model_dump()` shape (so callers in BFF or test fixtures don't need to
    reconstruct the model).
    """
    for tok in _tokens_for(camp):
        if tok in CAMPING_TOKENS:
            return True
    return False
