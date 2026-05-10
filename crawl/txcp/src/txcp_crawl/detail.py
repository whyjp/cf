"""Detail page crawler — fetch /resv/view.hbb?cseq={X} HTML and persist.

Strategy (per user "풍부한 로컬 데이터 우선"):
  1. Save raw HTML byte-for-byte to data/details_html/{cseq}.html (loss-free).
  2. Run a *minimal* parser to surface fields most reliably extractable today:
     - photos: src URLs from .swiper-slide img elements
     - title (page <title>)
     - any p_div_list_title/value pairs (4 labels seen on probe)
  3. Persist the parse result to data/details/{cseq}.json — ready for backend
     TxcpJsonlSource.get_detail to consume.

Better parsers (description / hashtags / facilities / reviews) are post-extraction:
the raw HTML stays in details_html/, so a richer parse can re-walk old files.

Self-contained polite client (does not depend on stealth.py.get_html which is
intentionally absent — keeps the blast radius narrow if stealth.py is changed
externally).
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import httpx
from loguru import logger
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from txcp_crawl.stealth import UA_POOL, DelayConfig


# magic-number-traceability: detail page path constant. Probed 2026-05-10:
# /resv/view.hbb?cseq={campSeq} returns 200 OK 130KB+ HTML for any list-API
# campSeq directly (cseq IS the list-API campSeq).
DETAIL_PATH = "/resv/view.hbb"

# magic-number-traceability: pages smaller than this are treated as "no such
# camp" alert pages (~500 bytes). Real detail pages are 120KB+.
_MIN_VALID_DETAIL_BYTES = 5000


@dataclass
class DetailRecord:
    cseq: str
    title: Optional[str]
    photos: list[str]
    label_value_pairs: dict[str, str]
    raw_html_path: str
    fetched_at: str

    def model_dump(self) -> dict:
        return {
            "cseq": self.cseq,
            "title": self.title,
            "photos": self.photos,
            "label_value_pairs": self.label_value_pairs,
            "raw_html_path": self.raw_html_path,
            "fetched_at": self.fetched_at,
        }


def parse_detail_html(html: str, cseq: str, raw_html_path: str) -> DetailRecord:
    """Minimal parser — title + photos + label/value rows. Loss-free fallback at
    raw_html_path for richer post-extraction."""
    tree = HTMLParser(html)

    title_el = tree.css_first("title")
    title = title_el.text(strip=True) if title_el else None

    photos: list[str] = []
    seen: set[str] = set()
    for img in tree.css(".swiper-slide img"):
        src = img.attributes.get("src") or img.attributes.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        if src in seen:
            continue
        seen.add(src)
        photos.append(src)

    titles = tree.css(".p_div_list_title")
    values = tree.css(".p_div_list_value")
    pairs: dict[str, str] = {}
    for t, v in zip(titles, values):
        k = t.text(strip=True)
        if k:
            pairs[k] = v.text(strip=True)

    return DetailRecord(
        cseq=cseq,
        title=title,
        photos=photos,
        label_value_pairs=pairs,
        raw_html_path=raw_html_path,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=45),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
    reraise=True,
)
async def _polite_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    last_call_holder: list,
    delay: DelayConfig,
    referer: str,
) -> httpx.Response:
    """Polite GET with UA rotation + jittered delay (mirrors stealth.post_form pattern)."""
    ua = random.choice(UA_POOL)
    elapsed = time.monotonic() - (last_call_holder[0] or 0)
    wait = random.uniform(delay.min_s, delay.max_s) - elapsed
    if wait > 0:
        await asyncio.sleep(wait)
    last_call_holder[0] = time.monotonic()
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "Referer": referer,
    }
    r = await client.get(url, headers=headers)
    if r.status_code in (429,) or r.status_code >= 500:
        r.raise_for_status()
    return r


async def fetch_one(
    client: httpx.AsyncClient,
    cseq: str,
    *,
    base_url: str,
    html_dir: Path,
    json_dir: Path,
    last_call_holder: list,
    delay: DelayConfig,
) -> Optional[DetailRecord]:
    """Fetch + persist one detail page. Idempotent (overwrites).
    Returns the DetailRecord on success, None on 4xx (camp not found / removed)."""
    url = f"{base_url}{DETAIL_PATH}?cseq={cseq}&only_able_yn="
    try:
        r = await _polite_get(
            client, url,
            last_call_holder=last_call_holder, delay=delay,
            referer=f"{base_url}/resv/list.hbb",
        )
    except httpx.HTTPStatusError as e:
        if 400 <= e.response.status_code < 500:
            logger.warning("detail cseq={} 4xx ({}) -- skip", cseq, e.response.status_code)
            return None
        raise

    raw_bytes = r.content
    if len(raw_bytes) < _MIN_VALID_DETAIL_BYTES:
        logger.warning(
            "detail cseq={} too small ({} bytes) -- likely 'no such camp' alert page",
            cseq, len(raw_bytes),
        )
        return None

    html_path = html_dir / f"{cseq}.html"
    html_dir.mkdir(parents=True, exist_ok=True)
    html_path.write_bytes(raw_bytes)

    text = raw_bytes.decode("utf-8", errors="replace")
    rec = parse_detail_html(text, cseq=cseq, raw_html_path=str(html_path.relative_to(html_dir.parent)))

    json_dir.mkdir(parents=True, exist_ok=True)
    json_path = json_dir / f"{cseq}.json"
    json_path.write_text(
        json.dumps(rec.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return rec


async def fetch_many(
    cseqs: Iterable[str],
    *,
    base_url: str = "https://m.thankqcamping.com",
    data_dir: Path = Path("data"),
    skip_existing: bool = True,
    timeout_s: float = 20.0,
) -> dict:
    """Pull many detail pages sequentially with polite delay.

    Returns: {fetched: N, skipped: M, missing: K, total_input: T}.
    """
    html_dir = data_dir / "details_html"
    json_dir = data_dir / "details"
    fetched = 0
    skipped = 0
    missing = 0

    cs_list = [str(c) for c in cseqs]
    logger.info("detail pull start -- total={} skip_existing={}", len(cs_list), skip_existing)

    delay = DelayConfig()
    last_call_holder: list = [0.0]
    try:
        import h2  # noqa: F401
        http2 = True
    except ImportError:
        http2 = False

    async with httpx.AsyncClient(
        timeout=timeout_s,
        follow_redirects=True,
        http2=http2,
    ) as client:
        for i, cs in enumerate(cs_list):
            target = json_dir / f"{cs}.json"
            if skip_existing and target.exists():
                skipped += 1
                if (skipped + fetched) % 100 == 0:
                    logger.info(
                        "progress {}/{}  fetched={} skipped={} missing={}",
                        i + 1, len(cs_list), fetched, skipped, missing,
                    )
                continue
            try:
                rec = await fetch_one(
                    client, cs,
                    base_url=base_url,
                    html_dir=html_dir, json_dir=json_dir,
                    last_call_holder=last_call_holder, delay=delay,
                )
            except Exception as e:
                logger.error("cseq={} unexpected error: {}", cs, e)
                missing += 1
                continue
            if rec is None:
                missing += 1
            else:
                fetched += 1
            if (i + 1) % 50 == 0:
                logger.info(
                    "progress {}/{}  fetched={} skipped={} missing={}",
                    i + 1, len(cs_list), fetched, skipped, missing,
                )

    logger.info("detail pull done -- fetched={} skipped={} missing={}", fetched, skipped, missing)
    return {"fetched": fetched, "skipped": skipped, "missing": missing, "total_input": len(cs_list)}


def cseqs_from_camps_jsonl(jsonl_path: Path) -> list[str]:
    """Read crawl/txcp/data/camps.jsonl and yield each id (campSeq str, prefix-stripped)."""
    out: list[str] = []
    if not jsonl_path.exists():
        return out
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = obj.get("id")
            if not cid:
                continue
            cid = str(cid)
            # Strip "txcp:" namespace prefix if present (TxcpJsonlSource adds it)
            if cid.startswith("txcp:"):
                cid = cid[5:]
            out.append(cid)
    return out
