"""Load detail/reviews/embedding into RocksDB (multi-prefix) and enrich FalkorDB.

RocksDB keyspace:
    camp:{id}             — list-view summary (existing, from camps_dedup.json)
    detail:{id}           — full /v1/camps/{id} payload
    reviews:{id}          — first page (top-N by 'recommend')
    embed:{id}            — concatenated embedding-ready text

FalkorDB enrichments:
    Camp.description, Camp.address, Camp.address_full
    Camp.numOfViewed, Camp.bookmarkCount, Camp.numOfReviews
    (c)-[:HAS_HASHTAG]->(:Hashtag)
    (c)-[:HAS_LOCATION]->(:LocationType)            ← real source for valley flag
    (c)-[:HAS_FACILITY]->(:Facility) supersede     ← real source for trampoline flag
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from falkordb import FalkorDB


HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
DETAILS_DIR = DATA / "details"
REVIEWS_DIR = DATA / "reviews"

ROCKS_BASE = "http://localhost:8071"
FALKOR_HOST, FALKOR_PORT, FALKOR_GRAPH = "localhost", 6379, "camfit"
TOP_REVIEWS_FOR_EMBED = 5


def build_embed_text(detail: dict, reviews: dict | None) -> str:
    """Concatenate name + address + brief + description + top reviews + hashtags."""
    parts: list[str] = []
    name = detail.get("name") or ""
    parts.append(f"# {name}")
    addr = " ".join(filter(None, [detail.get("address1"), detail.get("address2")])) or " ".join(
        filter(None, [detail.get("city"), detail.get("major")])
    )
    if addr:
        parts.append(f"주소: {addr}")
    if detail.get("brief"):
        parts.append(f"한줄: {detail['brief']}")
    if detail.get("locationBrief"):
        parts.append(f"위치: {detail['locationBrief']}")

    types = detail.get("types") or []
    loctypes = detail.get("locationTypes") or []
    facilities = detail.get("facilities") or []
    additional = detail.get("additionalFacilities") or []
    hashtags = detail.get("hashtags") or []

    if types or loctypes:
        parts.append(
            "유형/위치: " + ", ".join(types + loctypes)
        )
    if facilities or additional:
        parts.append("시설: " + ", ".join(sorted(set(facilities + additional))))
    if hashtags:
        parts.append("태그: " + " ".join(f"#{h}" for h in hashtags))

    desc = (detail.get("description") or "").strip()
    if desc:
        parts.append("\n## 소개")
        parts.append(desc)

    if reviews:
        items = sorted(
            reviews.get("reviews") or [],
            key=lambda r: -(r.get("totalScore") or 0),
        )[:TOP_REVIEWS_FOR_EMBED]
        if items:
            parts.append(f"\n## 리뷰 ({len(items)})")
            for i, rv in enumerate(items, 1):
                user = (rv.get("user") or {}).get("nickname") or "익명"
                score = rv.get("totalScore", "?")
                season = rv.get("season") or ""
                text = (rv.get("text") or "").strip()
                if not text:
                    continue
                parts.append(f"\n[{i}] {user} · {season} · {score}\n{text}")

    return "\n".join(parts)


def push_rocks(client: httpx.Client, key: str, value: dict | str) -> bool:
    if isinstance(value, str):
        body = {"_text": value}  # rocks server expects JSON; wrap text
    else:
        body = value
    try:
        r = client.put(f"{ROCKS_BASE}/kv/{key}", json=body)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"  rocks PUT {key} fail: {e}")
        return False


CY_ENRICH = """
MATCH (c:Camp {id: $id})
SET c.description = $description,
    c.address = $address,
    c.brief = $brief,
    c.locationBrief = $locationBrief,
    c.contact = $contact,
    c.numOfViewed = $numOfViewed,
    c.bookmarkCount = $bookmarkCount,
    c.numOfReviews = $numOfReviews,
    c.priceStartFrom = $priceStartFrom,
    c.priceEndTo = $priceEndTo,
    c.has_valley = $has_valley,
    c.has_kids = $has_kids,
    c.has_trampoline = $has_trampoline
WITH c
UNWIND $hashtags AS h
MERGE (ht:Hashtag {name: h})
MERGE (c)-[:HAS_HASHTAG]->(ht)
WITH c
UNWIND $locationTypes AS lt
MERGE (loc:LocationType {name: lt})
MERGE (c)-[:HAS_LOCATION]->(loc)
WITH c
UNWIND $facilities AS f
MERGE (ff:Facility {name: f})
MERGE (c)-[:HAS_FACILITY]->(ff)
"""


def main() -> int:
    detail_files = sorted(DETAILS_DIR.glob("*.json"))
    print(f"[load-rich] details: {len(detail_files)}")

    g = FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(FALKOR_GRAPH)
    rich_n = 0
    embed_n = 0
    rocks_d = 0
    rocks_r = 0
    rocks_e = 0
    with httpx.Client(timeout=20.0) as cli:
        for df in detail_files:
            cid = df.stem
            try:
                detail = json.loads(df.read_text(encoding="utf-8"))
            except Exception:
                continue
            rf = REVIEWS_DIR / f"{cid}.json"
            reviews = None
            if rf.exists():
                try:
                    reviews = json.loads(rf.read_text(encoding="utf-8"))
                except Exception:
                    reviews = None

            # 1) push raw detail + reviews to RocksDB
            if push_rocks(cli, f"detail:{cid}", detail):
                rocks_d += 1
            if reviews and push_rocks(cli, f"reviews:{cid}", reviews):
                rocks_r += 1

            # 2) embedding-ready text
            embed_text = build_embed_text(detail, reviews)
            if push_rocks(cli, f"embed:{cid}", embed_text):
                rocks_e += 1
            embed_n += 1

            # 3) FalkorDB enrich
            loc_types = list(detail.get("locationTypes") or [])
            facilities = sorted(set((detail.get("facilities") or []) + (detail.get("additionalFacilities") or [])))
            has_valley = "valley" in loc_types or any("valley" in (s or "") for s in (detail.get("surroundingLeisureTypes") or []) + (detail.get("leisureTypes") or []))
            has_trampoline = "trampoline" in facilities
            ks = " ".join((detail.get("hashtags") or []) + [detail.get("name") or "", detail.get("description") or ""])
            has_kids = any(k in ks for k in ("키즈", "어린이", "아이"))

            try:
                g.query(CY_ENRICH, params={
                    "id": cid,
                    "description": (detail.get("description") or "")[:8000],
                    "address": " ".join(filter(None, [detail.get("address1"), detail.get("address2")])) or None,
                    "brief": detail.get("brief") or None,
                    "locationBrief": detail.get("locationBrief") or None,
                    "contact": detail.get("contact") or None,
                    "numOfViewed": int(detail.get("numOfViewed") or 0),
                    "bookmarkCount": int(detail.get("bookmarkCount") or 0),
                    "numOfReviews": int((reviews or {}).get("pagination", {}).get("total") or detail.get("numOfReviews") or 0),
                    "priceStartFrom": int(detail.get("priceStartFrom") or 0),
                    "priceEndTo": int(detail.get("priceEndTo") or 0),
                    "has_valley": bool(has_valley),
                    "has_kids": bool(has_kids),
                    "has_trampoline": bool(has_trampoline),
                    "hashtags": list(detail.get("hashtags") or []),
                    "locationTypes": loc_types,
                    "facilities": facilities,
                })
                rich_n += 1
            except Exception as e:
                print(f"  KG enrich {cid} fail: {e}")

    summary = {}
    for label in ("Camp", "Region", "Category", "Facility", "Hashtag", "LocationType"):
        try:
            rs = g.query(f"MATCH (n:{label}) RETURN count(n)").result_set
            summary[label] = int(rs[0][0]) if rs else 0
        except Exception:
            summary[label] = "err"

    print(f"[done]")
    print(f"  RocksDB PUT: detail={rocks_d}  reviews={rocks_r}  embed={rocks_e}")
    print(f"  KG enriched: {rich_n}/{len(detail_files)}")
    print(f"  Graph node counts: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
