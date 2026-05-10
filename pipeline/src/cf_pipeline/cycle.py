"""End-to-end maintenance cycle — sustainable, idempotent, exception-tolerant.

Each stage handles its own data processing + migration. The cycle:
  1. ingest_camps --incremental    : skip ids already in PG, return new_ids
  2. embed --ids new_ids           : encode only newly-ingested camps (X3)
  3. extract_desc --ids new_ids    : description-derived signals for new camps (X3)
  4. extract_review per camp       : review-derived signals for new camps (per-camp idempotent)
  5. extract_filter (full)         : collection taxonomy (cheap full re-derive)
  6. refresh_aggregated (full)     : view refresh
  7. discover_themes (full)        : HDBSCAN over all embeddings (distribution-dependent)
  8. compute_marks (full)          : quantile bucketing per axis (distribution-dependent)
  9. rebuild_graph --ids new_ids   : partial graph update for new nodes (X2)

Idempotent throughout: re-run is safe. Stages 5-8 are full re-runs because
their algorithms are distribution-dependent (quantile / cluster boundaries).
This is fast enough (~seconds-minutes for thousands of camps) that the partial-
update tradeoff is not worth the complexity.

Exception policy:
  - Each stage wraps in try/except. On error: log + record in result dict
    + continue to next stage (so a single stage failure does not abort the
    cycle and leave data in inconsistent state). Caller inspects result for
    per-stage status.
  - All stages are idempotent — a stage that failed mid-write can be safely
    re-attempted.
  - With concurrent backends running, this only briefly disrupts service
    (graph reset is the only "wipe" + brief unavailable window).

Use:
    cf-pipeline cycle --source txcp                # both crawl sources implicit (ingest both)
    cf-pipeline cycle --source camfit
    cf-pipeline cycle --skip discover_themes,compute_marks   # heavy stages off
    cf-pipeline cycle --dry-run                              # plan only
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Literal

from rich.console import Console

from cf_be_api.container import Container
from cf_be_api.settings import Settings
from cf_pipeline import ingest_camps as ingest_camps_mod

Source = Literal["camfit", "txcp", "both"]

STAGES = [
    "ingest_camps",
    "embed",
    "extract_desc",
    "extract_review",
    "extract_filter",
    "refresh_aggregated",
    "discover_themes",
    "compute_marks",
    "rebuild_graph",
]


def _safe(label: str, fn, console: Console) -> dict:
    """Run `fn`, capture exception. Returns {'ok': bool, 'elapsed_s': float, 'result'/'error': ...}.
    Does not raise — caller inspects result['ok'] and chooses to abort or continue.
    """
    t0 = time.time()
    try:
        result = fn()
        elapsed = time.time() - t0
        console.print(f"[{label}] OK in {elapsed:.1f}s -> {result}")
        return {"ok": True, "elapsed_s": elapsed, "result": result}
    except Exception as e:
        elapsed = time.time() - t0
        console.print(f"[{label}] FAIL in {elapsed:.1f}s -> {type(e).__name__}: {e}")
        return {"ok": False, "elapsed_s": elapsed, "error": f"{type(e).__name__}: {e}"}


def run(
    source: Source = "both",
    *,
    camfit_data: Path = Path("crawl/camfit/data"),
    txcp_data: Path = Path("crawl/txcp/data"),
    skip: list[str] | None = None,
    dry_run: bool = False,
    full: bool = False,
) -> dict:
    """Execute the maintenance cycle.

    full=True: do not use --incremental on ingest; full re-upsert. Useful first
    time after schema change. Default False = incremental.
    skip=[...]: stage names to omit.
    """
    skip = skip or []
    console = Console()
    out: dict = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "stages": {}}

    if dry_run:
        for stage in STAGES:
            mark = "skip" if stage in skip else "RUN"
            console.print(f"  {mark}  {stage}")
        out["dry_run"] = True
        return out

    s = Settings(data_source="local-replay")
    c = Container(s)
    new_ids: list[str] = []
    try:
        # 1. ingest_camps (incremental by default)
        if "ingest_camps" not in skip:
            ingest_res = _safe(
                "ingest_camps",
                lambda: ingest_camps_mod.run(
                    source=source,
                    camfit_data=camfit_data,
                    txcp_data=txcp_data,
                    incremental=not full,
                ),
                console,
            )
            out["stages"]["ingest_camps"] = ingest_res
            if ingest_res.get("ok"):
                # collect new_ids across sources
                for src_name, src_res in (ingest_res.get("result") or {}).items():
                    new_ids.extend(src_res.get("new_ids") or [])
        # If full: every camp is "new" for downstream; pass None to mean "all"
        downstream_ids = new_ids if (not full and new_ids) else None
        out["new_ids"] = new_ids

        # 2. embed (ids=)
        if "embed" not in skip:
            out["stages"]["embed"] = _safe(
                "embed", lambda: c.build_embeddings().execute(ids=downstream_ids), console,
            )

        # 3. extract_desc (ids=)
        if "extract_desc" not in skip:
            out["stages"]["extract_desc"] = _safe(
                "extract_desc",
                lambda: c.extract_desc_signals().execute(ids=downstream_ids),
                console,
            )

        # 4. extract_review (per-camp; for new ids only if incremental, else all)
        if "extract_review" not in skip:
            uc = c.extract_review_signals()
            target_ids = downstream_ids or [camp.id for camp in c.camps_read.iter_all()]
            def _run_review() -> int:
                total = 0
                for cid in target_ids:
                    try:
                        total += uc.execute(cid)
                    except Exception:
                        # per-camp failure → skip this camp, keep going
                        pass
                return total
            out["stages"]["extract_review"] = _safe("extract_review", _run_review, console)

        # 5. extract_filter (full only — collection taxonomy)
        if "extract_filter" not in skip:
            out["stages"]["extract_filter"] = _safe(
                "extract_filter",
                lambda: c.extract_filter_signals().execute(workers=1),
                console,
            )

        # 6. refresh_aggregated
        if "refresh_aggregated" not in skip:
            out["stages"]["refresh_aggregated"] = _safe(
                "refresh_aggregated",
                lambda: (c.refresh_aggregated().execute() or "ok"),
                console,
            )

        # 7. discover_themes (full — HDBSCAN over all embeddings)
        if "discover_themes" not in skip:
            out["stages"]["discover_themes"] = _safe(
                "discover_themes", lambda: c.discover_themes().execute(), console,
            )

        # 8. compute_marks (full — quantile)
        if "compute_marks" not in skip:
            out["stages"]["compute_marks"] = _safe(
                "compute_marks", lambda: c.compute_marks().execute(), console,
            )

        # 9. rebuild_graph (incremental on new_ids; else full wipe+rewrite)
        if "rebuild_graph" not in skip:
            kwargs = {"ids": downstream_ids} if downstream_ids else {}
            out["stages"]["rebuild_graph"] = _safe(
                "rebuild_graph", lambda: c.rebuild_graph().execute(**kwargs), console,
            )

    finally:
        c.close()

    out["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    out["all_ok"] = all(s.get("ok") for s in out["stages"].values())
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["camfit", "txcp", "both"], default="both")
    parser.add_argument("--camfit-data", type=Path, default=Path("crawl/camfit/data"))
    parser.add_argument("--txcp-data", type=Path, default=Path("crawl/txcp/data"))
    parser.add_argument("--skip", default="", help="comma-separated stage names to skip")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--full", action="store_true",
                        help="Disable incremental on ingest (full re-upsert + downstream over all camps).")
    args = parser.parse_args()
    skip = [s.strip() for s in args.skip.split(",") if s.strip()]
    res = run(
        source=args.source,
        camfit_data=args.camfit_data,
        txcp_data=args.txcp_data,
        skip=skip,
        dry_run=args.dry_run,
        full=args.full,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("all_ok", False) or res.get("dry_run") else 1


if __name__ == "__main__":
    raise SystemExit(main())
