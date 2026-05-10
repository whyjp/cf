"""Crawler — 페이지네이션 루프 + dedup + 누적 + 4xx budget 가드."""
from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
from loguru import logger

from txcp_crawl import state as state_mod
from txcp_crawl.adapter import TkcpAdapter
from txcp_crawl.csv_writer import write_camps_csv
from txcp_crawl.fetcher import HttpxFetcher
from txcp_crawl.models import CampRecord
from txcp_crawl.settings import Settings


@dataclass
class PullSummary:
    pages_fetched: int
    new_records: int
    skipped_duplicates: int
    total_persisted: int
    total_count_reported: int
    stopped_reason: str


def _seen_from_jsonl(jsonl_path: Path) -> set[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    if not jsonl_path.exists():
        return seen
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                src = obj.get("source") or "thankqcamping"
                cid = obj.get("id") or obj.get("campSeq")
                if cid is not None:
                    seen.add((str(src), str(cid)))
            except json.JSONDecodeError:
                continue
    return seen


def _append_jsonl(jsonl_path: Path, records: list[CampRecord]) -> None:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(rec.model_dump_json() + "\n")


# magic-number-traceability: 4xx budget — page 10 윈도우에 4xx 2 회 이상 시 break (plan u1 §7 + I-4)
_RECENT_WINDOW = 10
_RECENT_4XX_THRESHOLD = 2


async def pull(
    *,
    site_tp: str | None = None,
    max_pages: int | None = None,
    resume: bool = True,
    settings: Settings | None = None,
) -> PullSummary:
    settings = settings or Settings()
    data_dir: Path = settings.data_dir
    jsonl_path = data_dir / "camps.jsonl"
    csv_path = data_dir / "camps.csv"
    state_path = data_dir / "state.json"

    cap = max_pages if max_pages is not None else settings.max_pages_default

    pull_state = state_mod.load(state_path) if resume else state_mod.PullState.fresh()
    if not resume:
        pull_state = state_mod.PullState.fresh()

    seen = _seen_from_jsonl(jsonl_path)
    initial_seen = len(seen)
    logger.info("txcp pull start — last_page={} seen_loaded={} cap={}", pull_state.last_page, initial_seen, cap)

    adapter = TkcpAdapter()
    fetcher = HttpxFetcher(base_url=settings.base_url, timeout_s=settings.request_timeout_s)
    await fetcher.open()

    pages_fetched = 0
    new_records = 0
    skipped_dup = 0
    total_count_reported = 0
    stopped = "completed"
    recent_status: deque[int] = deque(maxlen=_RECENT_WINDOW)

    try:
        page_num = pull_state.last_page + 1
        empty_streak = 0
        while page_num <= cap:
            payload = adapter.build_payload(page_num, site_tp)
            try:
                resp = await fetcher.post_form(adapter.LIST_PATH, payload)
                recent_status.append(200)
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                recent_status.append(code)
                if 400 <= code < 500:
                    recent_4xx = sum(1 for c in recent_status if 400 <= c < 500)
                    if recent_4xx >= _RECENT_4XX_THRESHOLD:
                        logger.warning("4xx budget exceeded ({} in last {} pages) — break", recent_4xx, _RECENT_WINDOW)
                        stopped = "4xx_budget"
                        break
                    logger.warning("4xx on page {} (will continue)", page_num)
                    page_num += 1
                    continue
                stopped = f"http_error_{code}"
                logger.error("HTTP error {} on page {} — abort", code, page_num)
                break

            try:
                result = adapter.parse_camp_list_response(resp)
            except ValueError as e:
                logger.error("Parse error on page {}: {}", page_num, e)
                stopped = "parse_error"
                break

            pages_fetched += 1
            total_count_reported = max(total_count_reported, result.total_count)

            if not result.records:
                empty_streak += 1
                # magic-number-traceability: 3 빈 page 연속 = 정상 stop (plan u1 §7 / refresh-2 r2 S5)
                if empty_streak >= 3:
                    stopped = "empty_streak"
                    break
                page_num += 1
                continue
            empty_streak = 0

            new_in_page: list[CampRecord] = []
            for rec in result.records:
                key = rec.dedup_key()
                if key in seen:
                    skipped_dup += 1
                    continue
                seen.add(key)
                new_in_page.append(rec)

            if new_in_page:
                _append_jsonl(jsonl_path, new_in_page)
                write_camps_csv(csv_path, new_in_page, append=True)
            new_records += len(new_in_page)

            pull_state.last_page = page_num
            pull_state.total_seen = len(seen)
            state_mod.save(state_path, pull_state)
            logger.info(
                "page {} — got {} records, {} new, {} dup, total_seen={}",
                page_num,
                len(result.records),
                len(new_in_page),
                len(result.records) - len(new_in_page),
                len(seen),
            )

            # magic-number-traceability: 3 마진 = 사이트 새 등록 흡수 (plan u1 §7 totalCount stop)
            if total_count_reported and len(seen) >= total_count_reported - 3:
                stopped = "total_reached"
                break
            page_num += 1

        if page_num > cap:
            stopped = "max_pages_cap"

    finally:
        await fetcher.close()
        pull_state.completed_at = datetime.now(timezone.utc).isoformat()
        state_mod.save(state_path, pull_state)

    return PullSummary(
        pages_fetched=pages_fetched,
        new_records=new_records,
        skipped_duplicates=skipped_dup,
        total_persisted=len(seen),
        total_count_reported=total_count_reported,
        stopped_reason=stopped,
    )
