"""CLI — typer entry point. 명령: pull / dedup-csv / inspect-page."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer
from loguru import logger

from tkcp_crawl import crawler as crawler_mod
from tkcp_crawl.adapter import TkcpAdapter
from tkcp_crawl.csv_writer import write_camps_csv
from tkcp_crawl.fetcher import HttpxFetcher
from tkcp_crawl.models import CampRecord
from tkcp_crawl.settings import Settings

app = typer.Typer(no_args_is_help=True, add_completion=False, help="tkcp-crawl — m.thankqcamping.com 캠핑장 크롤러")


def _setup_logger(level: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level)


@app.command()
def pull(
    site_tp: str = typer.Option(None, help="카테고리 코드 (BB000=오토캠핑 / BB001=글램핑 / BB002=카라반 / BB003=펜션 / BB006=피크닉). default=전체."),
    max_pages: int = typer.Option(None, help="안전 cap. default=settings.max_pages_default (600)."),
    resume: bool = typer.Option(True, help="state.json 의 last_page 부터 재개."),
) -> None:
    settings = Settings()
    _setup_logger(settings.log_level)
    try:
        summary = asyncio.run(
            crawler_mod.pull(site_tp=site_tp, max_pages=max_pages, resume=resume, settings=settings)
        )
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt — state saved.")
        raise typer.Exit(code=130)
    except OSError as e:
        logger.error("disk error: {}", e)
        raise typer.Exit(code=3)
    typer.echo(json.dumps(summary.__dict__, ensure_ascii=False, indent=2))


@app.command("dedup-csv")
def dedup_csv() -> None:
    """data/camps.jsonl → data/camps.csv 일괄 재생성."""
    settings = Settings()
    _setup_logger(settings.log_level)
    jsonl_path = settings.data_dir / "camps.jsonl"
    csv_path = settings.data_dir / "camps.csv"
    if not jsonl_path.exists():
        typer.echo(f"jsonl not found: {jsonl_path}", err=True)
        raise typer.Exit(code=1)
    seen: set[tuple[str, str]] = set()
    records: list[CampRecord] = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                rec = CampRecord.model_validate(obj)
            except Exception:
                continue
            key = rec.dedup_key()
            if key in seen:
                continue
            seen.add(key)
            records.append(rec)
    csv_path.write_text("", encoding="utf-8")  # truncate
    n = write_camps_csv(csv_path, records, append=False)
    typer.echo(f"wrote {n} rows -> {csv_path}")


@app.command("inspect-page")
def inspect_page(
    page_num: int = typer.Argument(..., help="가져올 페이지 번호 (1-based)."),
    site_tp: str = typer.Option(None, help="카테고리 필터."),
) -> None:
    """단일 페이지 응답을 stdout 으로 dump (디버그용)."""
    settings = Settings()
    _setup_logger(settings.log_level)

    async def _run() -> None:
        adapter = TkcpAdapter()
        fetcher = HttpxFetcher(base_url=settings.base_url)
        await fetcher.open()
        try:
            payload = adapter.build_payload(page_num, site_tp)
            raw = await fetcher.post_form(adapter.LIST_PATH, payload)
            result = adapter.parse_camp_list_response(raw)
        finally:
            await fetcher.close()
        out = {
            "page_num": page_num,
            "total_count_reported": result.total_count,
            "records_in_page": len(result.records),
            "first_record": result.records[0].model_dump(mode="json") if result.records else None,
        }
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2, default=str))

    asyncio.run(_run())


if __name__ == "__main__":
    app()
