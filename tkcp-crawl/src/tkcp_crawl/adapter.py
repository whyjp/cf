"""TkcpAdapter — site-specific build_payload + parse_camp_list_response.

이 모듈만 사이트 종속. 다른 모듈 (models, csv_writer, stealth, state) 은 사이트 무관.
후속 `crawlers/_shared/` 분리 시 본 모듈은 `crawlers/tkcp/adapter.py` 로 이동.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import NamedTuple

from loguru import logger
from pydantic import ValidationError

from tkcp_crawl.models import CampRecord


class ListPageResult(NamedTuple):
    records: list[CampRecord]
    total_count: int
    has_next: bool


class TkcpAdapter:
    """m.thankqcamping.com 어댑터.

    Endpoint (FINDINGS.md):
      POST /resv/ax_list_search.hbb
      Content-Type: application/x-www-form-urlencoded
      Response: {"code":200, "data":{"totalCount":int, "campList":[Camp(...)]}}
    """

    BASE_URL = "https://m.thankqcamping.com"
    LIST_PATH = "/resv/ax_list_search.hbb"

    def build_payload(self, page_num: int, site_tp: str | None = None) -> dict[str, str]:
        # FINDINGS.md §2 minimum payload — 필수 4 필드 + 카테고리 옵션.
        payload: dict[str, str] = {
            "page_num": str(page_num),
            "view_type": "PIC",
            "ser_st": "N",
            "is_empty_button": "N",
        }
        if site_tp:
            payload["ser_site_tp"] = site_tp
        return payload

    def parse_camp_list_response(self, raw: dict) -> ListPageResult:
        if not isinstance(raw, dict) or raw.get("code") != 200:
            raise ValueError(f"Unexpected response shape: code={raw.get('code') if isinstance(raw, dict) else type(raw)}")
        data = raw.get("data") or {}
        total = int(data.get("totalCount", 0))
        camps_raw = data.get("campList") or []
        records: list[CampRecord] = []
        pulled_at = datetime.now(timezone.utc)
        for camp in camps_raw:
            if not isinstance(camp, dict):
                continue
            try:
                # thumbnail: campPicList[0].imgUrl (sort=0 정렬 가정)
                pic_list = camp.get("campPicList") or []
                thumb = None
                if pic_list:
                    sorted_pics = sorted(pic_list, key=lambda p: p.get("sort", 0))
                    thumb = sorted_pics[0].get("imgUrl") if sorted_pics else None
                rec = CampRecord.model_validate({**camp, "thumbnail": thumb, "pulled_at": pulled_at})
            except ValidationError as e:
                logger.warning("skip record (validation): campSeq={} err={}", camp.get("campSeq"), str(e)[:200])
                continue
            records.append(rec)
        has_next = len(camps_raw) > 0
        return ListPageResult(records=records, total_count=total, has_next=has_next)
