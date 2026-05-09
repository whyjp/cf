"""camfit-puller CLI — typer entry point with 4 subcommands."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from . import __version__
from .crawler import CrawlConfig, crawl
from .csv_writer import read_rows, write_rows
from .falkor_writer import count_summary, reset_and_load

app = typer.Typer(help="camfit.co.kr 폴라이트 크롤러 + 지식그래프/PG 적재 + FE serve")
console = Console()


@app.callback()
def _root(version: bool = typer.Option(False, "--version", help="버전 출력")) -> None:
    if version:
        console.print(f"camfit-puller {__version__}")
        raise typer.Exit()


@app.command(name="crawl")
def crawl_cmd(
    out: Path = typer.Option(Path("data/camfit.csv"), "--out", "-o", help="출력 CSV 경로"),
    page_size: int = typer.Option(50, help="페이지 크기"),
    max_pages: int = typer.Option(200, help="최대 페이지 수"),
    discover_only: bool = typer.Option(False, help="endpoint 만 확인하고 종료"),
) -> None:
    """camfit.co.kr 전수 크롤 → CSV. 예의 수준 stealth 적용."""

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


@app.command("load-falkor")
def load_falkor(
    csv_path: Path = typer.Option(Path("data/camfit.csv"), "--csv", help="입력 CSV"),
    host: str = typer.Option("localhost", help="FalkorDB host"),
    port: int = typer.Option(6379, help="FalkorDB port"),
    graph: str = typer.Option("camfit", help="그래프 이름"),
) -> None:
    """CSV → FalkorDB 지식그래프 재구축 (graph reset + load)."""
    recs = read_rows(csv_path)
    camps, stmts = reset_and_load(recs, host=host, port=port, graph=graph)
    summary = count_summary(host=host, port=port, graph=graph)
    console.print(f"[falkor] graph '{graph}' rebuilt: {camps} camps / {stmts} statements")
    console.print(f"[falkor] counts: {summary}")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="bind"),
    port: int = typer.Option(8070, help="포트"),
    reload: bool = typer.Option(False, help="dev reload"),
) -> None:
    """FE static + read API 서비스."""
    import uvicorn

    uvicorn.run("camfit_puller.api:app", host=host, port=port, reload=reload)


@app.command()
def info() -> None:
    """현재 설정 / 헬스 출력."""
    from .api import healthz
    console.print({"version": __version__, "health": healthz()})


if __name__ == "__main__":
    app()
