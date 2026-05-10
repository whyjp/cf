"""CLI — typer entry point. 명령: pull / dedup-csv / inspect-page."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer
from loguru import logger

from txcp_crawl import crawler as crawler_mod
from txcp_crawl import detail as detail_mod
from txcp_crawl.adapter import TkcpAdapter
from txcp_crawl.csv_writer import write_camps_csv
from txcp_crawl.fetcher import HttpxFetcher
from txcp_crawl.models import CampRecord
from txcp_crawl.settings import Settings

app = typer.Typer(no_args_is_help=True, add_completion=False, help="txcp-crawl — m.thankqcamping.com 캠핑장 크롤러")


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


@app.command("detail")
def detail_cmd(
    cseq: list[str] = typer.Option(None, "--cseq", help="명시적 campSeq (반복 가능). 미지정 시 data/camps.jsonl 읽음."),
    limit: int = typer.Option(None, help="cseqs 의 첫 N 만 처리 (smoke 용)."),
    skip_existing: bool = typer.Option(True, help="data/details/{cseq}.json 이미 있으면 건너뜀."),
) -> None:
    """Per-camp detail page (view.hbb?cseq=X) crawl — raw HTML + minimal parse 적재.

    데이터:
      data/details_html/{cseq}.html  ← raw HTML byte-perfect (loss-free)
      data/details/{cseq}.json       ← minimal parse (title/photos/label_value_pairs)

    Examples:
        txcp-crawl detail --cseq 14870 --cseq 16706                  # 2개만
        txcp-crawl detail --limit 10                                  # camps.jsonl 첫 10
        txcp-crawl detail                                              # 전체 (~9,200, ~6.5h)
    """
    settings = Settings()
    _setup_logger(settings.log_level)

    if cseq:
        cseqs = list(cseq)
    else:
        jsonl = settings.data_dir / "camps.jsonl"
        cseqs = detail_mod.cseqs_from_camps_jsonl(jsonl)
        if not cseqs:
            typer.echo(f"no cseqs found (no --cseq and {jsonl} empty)", err=True)
            raise typer.Exit(code=1)

    if limit is not None:
        cseqs = cseqs[:limit]

    try:
        summary = asyncio.run(
            detail_mod.fetch_many(
                cseqs,
                base_url=settings.base_url,
                data_dir=settings.data_dir,
                skip_existing=skip_existing,
                timeout_s=settings.request_timeout_s,
            )
        )
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt -- partial data persisted.")
        raise typer.Exit(code=130)
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
