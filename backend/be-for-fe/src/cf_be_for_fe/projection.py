"""FE-friendly projection of be-api raw responses.

Moved from cf_be_api/api.py during SP-A sprint A3.
SP-D D-8 (cutover): inlined FEATURED_AXES — no longer imports from cf_be_api,
since be-api is now the Go binary. The Go side has its own equivalent registry
in `internal/domain/featured_axes.go`; both must be kept in sync when adding
a new axis. (Source-of-truth gate: a regression test compares the two.)
"""
from __future__ import annotations
from typing import Any, TypedDict

from .constants import _LANDLOCKED_SIDO, _MARITIME_TOKENS, _TYPE_KO


class FeaturedAxis(TypedDict):
    id: str            # snake_case, becomes r.has_<id>
    ko: str            # display label (Korean)
    icon: str          # emoji
    tone: str          # "" | "warm" | "bark"
    keywords: list[str]


# Inlined from former cf_be_api/domain/featured_axes.py (SP-D D-8 cutover).
# When adding an axis, mirror it in the Go side
# (backend/be-api/internal/domain/featured_axes.go).
FEATURED_AXES: list[FeaturedAxis] = [
    {"id": "valley",     "ko": "계곡",     "icon": "🌊", "tone": "",
     "keywords": ["valley", "계곡"]},
    {"id": "kids",       "ko": "키즈캠핑", "icon": "🧒", "tone": "warm",
     "keywords": ["kids", "키즈", "아이"]},
    {"id": "trampoline", "ko": "트램펄린", "icon": "🤸", "tone": "bark",
     "keywords": ["trampoline", "trampolin",
                  "트램펄린", "트램폴린", "트렘펄린", "트렘폴린", "트램벌린",
                  "방방", "퐁퐁"]},
    {"id": "halloween",  "ko": "할로윈",   "icon": "🎃", "tone": "warm",
     "keywords": ["할로윈", "핼러윈", "핼로윈", "halloween"]},
    {"id": "cherry",     "ko": "벚꽃",     "icon": "🌸", "tone": "warm",
     "keywords": ["벚꽃", "벚나무"]},
    {"id": "autumn",     "ko": "단풍",     "icon": "🍁", "tone": "bark",
     "keywords": ["단풍"]},
]

assert len({a["id"] for a in FEATURED_AXES}) == len(FEATURED_AXES), \
    "FEATURED_AXES has duplicate id"
for _a in FEATURED_AXES:
    assert _a["keywords"], f"FEATURED_AXES['{_a['id']}'] has empty keywords"
    assert _a["tone"] in ("", "warm", "bark"), \
        f"FEATURED_AXES['{_a['id']}'] has invalid tone {_a['tone']!r}"
del _a


def filter_maritime_for_inland(items, sido) -> list:
    """Drop maritime-flavoured items when the camp sits in a landlocked sido.

    Original: cf_be_api/api.py:_filter_maritime_for_inland
    """
    if not items or not sido or sido not in _LANDLOCKED_SIDO:
        return list(items or [])
    return [s for s in items if not any(tok in s for tok in _MARITIME_TOKENS)]


def filter_location_types_for_inland(loc_types, sido) -> list:
    """Drop ocean/island tags when the camp sits in a landlocked sido.

    Original: cf_be_api/api.py:_filter_location_types_for_inland
    """
    if not loc_types or not sido or sido not in _LANDLOCKED_SIDO:
        return list(loc_types or [])
    return [t for t in loc_types if t not in ("ocean", "island")]


def project_categories(collections, types) -> list[str]:
    """Compose the FE-facing `categories` chip list from camp.collections +
    camp.types. Three opaque crawler-discovery prefixes are dropped:
      - 전시:E*    camfit editorial bucket IDs (>500 camps each)
      - 시군구:*  admin-region path stamps from the crawler
      - 검색:*    keyword-search discovery stamps
    Camp types are translated to Korean.

    Original: cf_be_api/api.py:_project_categories
    """
    raw = list(collections or []) + [_TYPE_KO.get(t, t) for t in (types or [])]
    return [
        s for s in raw
        if not s.startswith("전시:")
        and not s.startswith("시군구:")
        and not s.startswith("검색:")
    ]


def camp_to_fe_row(c: dict) -> dict:
    """FE-friendly flat projection of a Camp domain dict (Camp.model_dump()).

    The map view in fe reads `r.lat`/`r.lon`/`r.sido` directly (no `.geo.lat`
    traversal), and the chip rendering iterates `r.categories`.

    Boolean axis flags `has_<id>` are generated dynamically from the
    module-level FEATURED_AXES list — adding a new axis there surfaces it on
    every row without further edits to this function. Each axis matches
    case-insensitive substrings against a haystack joined from every
    meaningful tag source plus description + brief. Mirror the axis in
    backend/be-api/internal/domain/featured_axes.go (Go side).

    Original: cf_be_api/api.py:_camp_to_fe_row (took a Camp model object).
    """
    geo = c.get("geo") or {}
    region = c.get("region") or {}
    sido = region.get("sido") if region else None
    cats = filter_maritime_for_inland(c.get("collections") or [], sido)
    facs = list(c.get("facilities") or []) + list(c.get("additional_facilities") or [])
    types = list(c.get("types") or [])
    location_types = filter_location_types_for_inland(c.get("location_types") or [], sido)
    hashtags = filter_maritime_for_inland(c.get("hashtags") or [], sido)

    # Search corpus for the boolean axis flags — every meaningful tag source
    # joined into one lowercased blob for substring matching. description+
    # brief join is what lets 할로윈/단풍 (mostly description-bound) light up.
    haystack = " ".join(
        cats + types + facs + location_types + hashtags
        + [c.get("description") or "", c.get("brief") or ""]
    ).lower()

    def _matches(*needles: str) -> bool:
        return any(n.lower() in haystack for n in needles)

    row = {
        "id": c.get("id"),
        "name": c.get("name"),
        "sido": sido,
        "sigungu": region.get("sigungu") if region else None,
        "address": c.get("address"),
        "lat": geo.get("lat") if geo else None,
        "lon": geo.get("lon") if geo else None,
        "categories": project_categories(cats, types),
        "facilities": facs,
        "location_types": location_types,
        "hashtags": hashtags,
        "num_of_reviews": c.get("num_of_reviews"),
        "bookmark_count": c.get("bookmark_count"),
        "url": c.get("url"),
    }
    # Dynamic has_<id> derivation from the featured-axis registry.
    for axis in FEATURED_AXES:
        row[f"has_{axis['id']}"] = _matches(*axis["keywords"])
    return row


def project_camps(rows: list[dict]) -> list[dict]:
    """Bulk projection of a /sites or /sites/search result list."""
    return [camp_to_fe_row(c) for c in rows]


def project_site_detail(d: dict) -> dict:
    """Project a /sites/{id} response (GetSiteDetail.execute() shape).

    Input dict shape:
        {
          "camp": Camp.model_dump(),
          "reviews_top": [Review.model_dump(), ...],
          "reviews_total": int,
          "concepts": [{"id":..,"score":..}, ...],
          "theme": {...} | None,
        }

    Returns the flat camelCase mix that the FE DetailPanel expects.

    Original: cf_be_api/api.py:site_detail handler body (lines 122-167).
    """
    camp = d.get("camp") or {}
    geo = camp.get("geo") or {}
    region = camp.get("region") or {}
    photos = camp.get("photos") or []
    sido = region.get("sido")
    return {
        "id": camp.get("id"),
        "name": camp.get("name"),
        "address": camp.get("address"),
        "lat": geo.get("lat"),
        "lon": geo.get("lon"),
        "region_sido": sido,
        "region_sigungu": region.get("sigungu"),
        "categories": filter_maritime_for_inland(
            project_categories(camp.get("collections"), camp.get("types")), sido,
        ),
        "facilities": list(camp.get("facilities") or []) + list(camp.get("additional_facilities") or []),
        "hashtags": filter_maritime_for_inland(camp.get("hashtags") or [], sido),
        "description": camp.get("description"),
        "brief": camp.get("brief"),
        "locationBrief": camp.get("location_brief"),
        "contact": camp.get("contact"),
        "priceStartFrom": camp.get("price_start_from"),
        "priceEndTo": camp.get("price_end_to"),
        "numOfReviews": camp.get("num_of_reviews"),
        "bookmarkCount": camp.get("bookmark_count"),
        "url": camp.get("url"),
        "photos": [
            {"url": p.get("url"), "thumb": p.get("thumb_url") or p.get("url")}
            for p in photos
        ],
        "reviews_total": d.get("reviews_total"),
        "reviews_top": [
            {
                "user": r.get("user_nick"),
                "season": r.get("season"),
                "userType": r.get("user_type"),
                "numOfDays": r.get("num_of_days"),
                "score": r.get("score"),
                "text": r.get("text"),
            }
            for r in (d.get("reviews_top") or [])
        ],
        "concepts": d.get("concepts") or [],
        "theme": d.get("theme"),
    }
