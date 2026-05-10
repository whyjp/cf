"""full_run --dry-run: must print plan + exit 0 without DB calls."""
from __future__ import annotations
import subprocess
import sys


def test_dry_run_exits_zero_with_plan_output():
    result = subprocess.run(
        [sys.executable, "-m", "cf_pipeline.full_run", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = result.stdout + result.stderr
    assert "ingest_camps" in out
    assert "geocode_run" in out
    assert "rebuild_graph" in out
    assert "derive_lexicon" in out
    assert "seed" in out


def test_only_flag_runs_subset():
    result = subprocess.run(
        [sys.executable, "-m", "cf_pipeline.full_run", "--dry-run", "--only", "ingest_camps"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert "ingest_camps" in out
    # Other stages should be skipped
    assert "skip" in out.lower() or "only" in out.lower()
