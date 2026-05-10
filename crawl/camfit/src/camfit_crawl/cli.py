"""camfit-crawl CLI — typer entry point (crawler-only).

Backend (FastAPI) and pipeline (P2 stages) commands have moved to
`backend/` and `pipeline/` packages respectively. This CLI keeps the
crawler-only commands.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from . import __version__
from .crawler import CrawlConfig, crawl
from .csv_writer import write_rows

app = typer.Typer(help="camfit-crawl — camfit.co.kr 폴라이트 크롤러")
console = Console()


@app.callback()
def _root(version: bool = typer.Option(False, "--version", help="버전 출력")) -> None:
    if version:
        console.print(f"camfit-crawl {__version__}")
        raise typer.Exit()


@app.command(name="crawl")
def crawl_cmd(
    out: Path = typer.Option(Path("data/camfit.csv"), "--out", "-o", help="출력 CSV 경로"),
    page_size: int = typer.Option(50, help="페이지 크기"),
    max_pages: int = typer.Option(200, help="최대 페이지 수"),
    discover_only: bool = typer.Option(False, help="endpoint 만 확인하고 종료"),
) -> None:
    """camfit.co.kr 크롤 → CSV (P1 utility — for filling data/* archives)."""
    async def _run() -> int:
        cfg = CrawlConfig(page_size=page_size, max_pages=max_pages, discover_only=discover_only)
        recs = []
        async for r in crawl(cfg):
            recs.append(r)
        if discover_only:
            console.print("[discover] done — 0 row written")
            return 0
        n = write_rows(recs, out)
        console.print(f"[csv] {n} rows → {out}")
        return n
    asyncio.run(_run())


if __name__ == "__main__":
    app()
