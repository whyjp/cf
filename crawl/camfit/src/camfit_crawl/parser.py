"""HTML / JSON → CampRecord parser.

NOTE — camfit.co.kr 의 *실제* 마크업 selector 는 site evolution 에 따라 변동.
본 모듈은 *방어적* 으로 구현: 여러 selector candidates 를 순서대로 시도하고
JSON 우선, HTML fallback. 사용자가 실 selector 가 깨지면 SELECTORS 만 수정.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable, Optional

from selectolax.parser import HTMLParser

from .models import CampRecord


# Selector 우선순위 — 첫 매치가 우선. 실 사이트 점검 시 보강 가능.
SELECTORS = {
    "card": [
        "li.camp-card",
        "div.camp-card",
        "a.camp-link",
        "[data-camp-id]",
        # React/MUI 홈: 명시 카드 없을 때 캠프 상세 링크를 카드로 간주
        'a[href^="/camp/"]',
    ],
    "id_attr": ["data-camp-id", "data-id", "id"],
    "name": [
        ".camp-name",
        'p[class*="typography-bold"]',
        "p.typography-bold",
        "h3",
        ".title",
    ],
    "region": [".region", ".address", ".camp-region"],
    "category_tag": [".tag", ".category", ".chip"],
    "facility_tag": [".facility", ".feature"],
    "image": ["img.thumb", "img"],
    "link": ["a[href]"],
}

KIDS_KEYWORDS = ("키즈", "어린이", "kid", "kids")
VALLEY_KEYWORDS = ("계곡", "valley", "stream", "creek")
TRAMPOLINE_KEYWORDS = ("트램펄린", "trampoline", "방방")
SIDO_PATTERN = re.compile(
    r"(서울|부산|대구|인천|광주|대전|울산|세종|"
    r"경기|강원|충북|충남|전북|전남|경북|경남|제주)"
)
SIGUNGU_PATTERN = re.compile(r"(\S+?[시군구])")

# 신규 SPA 는 /camp/<MongoDB ObjectId 24 hex> 패턴이 대부분. /camp/exhibition 등 메타 페이지 제외용.
_CAMP_OID_RE = re.compile(r"^[a-fA-F\d]{24}$")


def _first_text(node, sels: list[str]) -> Optional[str]:
    for s in sels:
        n = node.css_first(s)
        if n is not None:
            t = n.text(strip=True)
            if t:
                return t
    return None


def _first_attr(node, sels: list[str], attr: str) -> Optional[str]:
    for s in sels:
        n = node.css_first(s)
        if n is not None and attr in n.attributes:
            return n.attributes.get(attr)
    return None


def _parse_id(node) -> Optional[str]:
    for attr in SELECTORS["id_attr"]:
        v = node.attributes.get(attr) if hasattr(node, "attributes") else None
        if v:
            return str(v)
    return None


def _classify_facilities(text: str) -> dict[str, bool]:
    low = text.lower()
    return {
        "has_valley": any(k in text or k.lower() in low for k in VALLEY_KEYWORDS),
        "has_kids": any(k in text or k.lower() in low for k in KIDS_KEYWORDS),
        "has_trampoline": any(k in text or k.lower() in low for k in TRAMPOLINE_KEYWORDS),
    }


def _split_region(addr: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not addr:
        return None, None
    sido_m = SIDO_PATTERN.search(addr)
    sigungu_m = SIGUNGU_PATTERN.search(addr)
    return (sido_m.group(1) if sido_m else None,
            sigungu_m.group(1) if sigungu_m else None)


def parse_list_html(html: str, base_url: str = "https://camfit.co.kr") -> list[CampRecord]:
    """Parse a camfit list page HTML → CampRecord list."""
    tree = HTMLParser(html)
    cards: list = []
    for sel in SELECTORS["card"]:
        cards = tree.css(sel)
        if cards:
            break

    out: list[CampRecord] = []
    seen_ids: set[str] = set()
    for card in cards:
        href_raw = (_first_attr(card, SELECTORS["link"], "href") or "").strip()
        cid_attr = _parse_id(card)
        if cid_attr:
            cid = str(cid_attr).split("/")[-1].split("?")[0]
        elif href_raw:
            cid = href_raw.split("/")[-1].split("?")[0]
            if not _CAMP_OID_RE.match(cid):
                continue
        else:
            continue
        if not cid:
            continue
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        raw_name = _first_text(card, SELECTORS["name"])
        img_alt = _first_attr(card, ["img"], "alt")
        name = (raw_name or "").strip() or (img_alt or "").strip() or "(이름 미상)"
        addr = _first_text(card, SELECTORS["region"])
        sido, sigungu = _split_region(addr)
        link = _first_attr(card, SELECTORS["link"], "href")
        url = link if (link and link.startswith("http")) else (base_url + (link or ""))
        img = _first_attr(card, SELECTORS["image"], "src")

        cats = [n.text(strip=True) for n in card.css(",".join(SELECTORS["category_tag"])) if n.text(strip=True)]
        facs = [n.text(strip=True) for n in card.css(",".join(SELECTORS["facility_tag"])) if n.text(strip=True)]
        merged_text = " ".join(cats + facs + [name, addr or ""])
        flags = _classify_facilities(merged_text)

        out.append(
            CampRecord(
                id=str(cid),
                name=name,
                url=url,
                region_sido=sido,
                region_sigungu=sigungu,
                address=addr,
                categories=sorted(set(cats)),
                facilities=sorted(set(facs)),
                raw_image_url=img,
                **flags,
            )
        )
    return out


def parse_list_json(payload: Any, base_url: str = "https://camfit.co.kr") -> list[CampRecord]:
    """Best-effort parser for a JSON listing endpoint.

    Accepts shapes:
      - {"items": [...]}, {"data": [...]}, {"camps": [...]} or top-level list.
    Each item must have at least 'id' / '_id' / 'campId' and 'name'.
    """
    items: Iterable[dict] = []
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        for key in ("items", "data", "camps", "results"):
            if isinstance(payload.get(key), list):
                items = payload[key]
                break

    out: list[CampRecord] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        cid = it.get("id") or it.get("_id") or it.get("campId")
        name = it.get("name") or it.get("title")
        if not cid or not name:
            continue

        addr = it.get("address") or it.get("location") or ""
        sido = it.get("sido") or _split_region(addr)[0]
        sigungu = it.get("sigungu") or _split_region(addr)[1]

        loc = it.get("location") or it.get("geo") or {}
        lat = it.get("lat") or it.get("latitude") or (loc.get("lat") if isinstance(loc, dict) else None)
        lon = it.get("lon") or it.get("lng") or it.get("longitude") or (loc.get("lng") if isinstance(loc, dict) else None)

        cats = list(it.get("categories", []) or it.get("tags", []) or [])
        facs = list(it.get("facilities", []) or it.get("features", []) or [])
        merged = " ".join(map(str, cats + facs + [name, addr or ""]))
        flags = _classify_facilities(merged)

        url = it.get("url") or f"{base_url}/camp/{cid}"
        out.append(
            CampRecord(
                id=str(cid),
                name=str(name),
                url=url,
                region_sido=sido,
                region_sigungu=sigungu,
                address=addr or None,
                lat=float(lat) if lat is not None else None,
                lon=float(lon) if lon is not None else None,
                categories=[str(c) for c in cats],
                facilities=[str(f) for f in facs],
                raw_image_url=it.get("image") or it.get("thumbnail"),
                **flags,
            )
        )
    return out


def detect_payload(text: str) -> str:
    """Return 'json' if `text` is parseable JSON, else 'html'."""
    s = text.lstrip()
    if not s:
        return "html"
    if s[0] in "{[":
        try:
            json.loads(text)
            return "json"
        except Exception:
            return "html"
    return "html"
