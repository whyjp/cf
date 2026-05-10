from __future__ import annotations
import hashlib
from .models import Camp, Review

TOP_N_REVIEWS = 5


def build_embed_text(camp: Camp, reviews: list[Review]) -> str:
    parts: list[str] = []
    parts.append(f"# {camp.name}")
    if camp.address:
        parts.append(f"주소: {camp.address}")
    if camp.brief:
        parts.append(f"한줄: {camp.brief}")
    if camp.location_brief:
        parts.append(f"위치: {camp.location_brief}")
    types_loc = camp.types + camp.location_types
    if types_loc:
        parts.append(f"유형: {', '.join(types_loc)}")
    facs = sorted(set(camp.facilities + camp.additional_facilities))
    if facs:
        parts.append(f"시설: {', '.join(facs)}")
    if camp.hashtags:
        parts.append(f"태그: {' '.join('#' + h for h in camp.hashtags)}")
    if camp.description:
        parts.append("\n## 소개")
        parts.append(camp.description.strip())
    top = sorted(
        [r for r in reviews if (r.text or "").strip()],
        key=lambda r: -(r.score or 0),
    )[:TOP_N_REVIEWS]
    if top:
        parts.append(f"\n## 리뷰 ({len(top)})")
        for i, rv in enumerate(top, 1):
            user = rv.user_nick or "익명"
            score = rv.score if rv.score is not None else "?"
            season = rv.season or ""
            parts.append(f"\n[{i}] {user} · {season} · {score}\n{rv.text.strip()}")
    return "\n".join(parts)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
