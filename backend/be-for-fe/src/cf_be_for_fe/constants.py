"""BFF constants — fe-friendly value sets.

Moved from cf_be_api/api.py during SP-A sprint A3 (projection 이전).
"""
from __future__ import annotations


# Sido (광역) values that have NO coastline — every camp here is purely
# inland. Camfit's source data sometimes tags lake-side camps as "ocean"
# and lake-island camps as "island" (e.g. 청풍호반 오토캠핑장 in 충북
# carries locationTypes=['lake','mountain','forest','river','ocean']).
# We drop maritime tags for these sidos at the FE projection layer.
_LANDLOCKED_SIDO = frozenset({
    "충북", "충청북도",
    "대전", "대전광역시",
    "세종", "세종특별자치시",
    "광주", "광주광역시",
    "대구", "대구광역시",
    "서울", "서울특별시",
})

# Substrings that indicate a maritime claim — collection names like
# "콜렉션:오션뷰 캠핑장" or hashtags like "바다캠핑장" get filtered out
# of `r.categories` when the camp's sido has no coast.
_MARITIME_TOKENS = ("오션", "바다", "섬캠", "해변", "해안")


# English camp-type codes from camfit's source data → Korean labels.
# Unknown codes pass through unchanged (better to surface than to drop).
_TYPE_KO = {
    "autoCamping": "오토캠핑", "pension": "펜션", "glamping": "글램핑",
    "caravan": "카라반", "bungalow": "방갈로", "rental": "렌탈",
    "carCamping": "차박", "experience": "체험", "trailer": "트레일러",
}
