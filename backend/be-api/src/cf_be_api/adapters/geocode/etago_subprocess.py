"""etago subprocess geocoder — implements ports.geocode.Geocoder.

All geo-related code lives in the etago Go binary (Naver NCP first, Kakao K1
as the landmark fallback). This adapter shells out to ``etago --geocode --json``
for one-off lookups and to ``etago --geocode --batch`` for fan-out across
many addresses (one process spawn for the whole pending queue).

The same binary is already used for ETA via :mod:`adapters.eta.etago_subprocess`,
so we share the binary-resolution logic and timeout conventions.
"""
from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass, field
from typing import Iterable, Optional

from ...domain.models import GeoPoint
from ..etago_bin import resolve_etago_bin, EtagoUnavailable  # re-exported

# Re-export for backwards-compatibility — earlier code imported EtagoUnavailable
# from this module.
__all__ = ["EtagoGeocoderSubprocess", "EtagoUnavailable"]


@dataclass
class EtagoGeocoderSubprocess:
    """Geocoder backed by the etago Go binary (Naver NCP + Kakao fallback).

    Single ``lookup`` calls are expensive (~10–30 ms of process startup +
    network); CachedGeocoder amortizes that for warm reads. Bulk crawls
    should call ``lookup_many`` which fans out under one subprocess.
    """

    # Empty default — __post_init__ resolves (and auto-builds) on first use.
    bin_path: str = ""
    per_query_timeout_s: float = 8.0
    # Total cap for a batch run. Bumped high because crawl post-processing
    # may legitimately resolve thousands of addresses in one go; the
    # internal worker pool keeps wall-clock bounded.
    batch_total_timeout_s: float = 600.0
    batch_workers: int = 8

    def __post_init__(self) -> None:
        if not self.bin_path:
            # Auto-build via shared resolver — surfaces a single
            # EtagoUnavailable with a clear remediation message.
            self.bin_path = resolve_etago_bin()

    # ───────────────────────── single lookup ─────────────────────────

    def lookup(self, address: str, *, hint: str | None = None) -> Optional[GeoPoint]:
        if not address:
            return None
        result = self._call_one(address)
        if result is None and hint:
            result = self._call_one(hint)
        return result

    def _call_one(self, query: str) -> Optional[GeoPoint]:
        cmd = [
            self.bin_path,
            "--geocode", "--json",
            "--timeout", f"{int(self.per_query_timeout_s)}s",
            query,
        ]
        payload = _run_async_blocking(self._spawn_capture(cmd))
        if payload is None:
            return None
        try:
            return GeoPoint(lat=float(payload["lat"]), lon=float(payload["lon"]))
        except (KeyError, TypeError, ValueError):
            return None

    async def _spawn_capture(self, cmd: list[str]) -> Optional[dict]:
        """Spawn etago, return parsed JSON or None on any failure."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError):
            return None
        try:
            stdout, _stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.per_query_timeout_s + 3
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return None
        if proc.returncode != 0:
            return None
        try:
            return json.loads(stdout.decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            return None

    # ───────────────────────── batch lookup ──────────────────────────

    def lookup_many(
        self, items: Iterable[tuple[str, str | None]],
    ) -> dict[str, Optional[GeoPoint]]:
        """Resolve many addresses under one ``etago --geocode --batch``.

        Naver / Kakao have no native batch endpoint, but spawning a single
        Go process and fanning out internally cuts the per-item cost from
        "one OS process per camp" to "shared TCP/HTTP connection pool +
        one stdin/stdout pipe". Same coords; ~50× faster wall-clock.
        """
        pairs = [(a, h) for a, h in items if a]
        out: dict[str, Optional[GeoPoint]] = {}
        if not pairs:
            return out

        # First-pass batch: address only. Collect failures keyed by index.
        primary = _run_async_blocking(self._spawn_batch([a for a, _ in pairs]))
        # primary is a list aligned with the input order.

        # Build map by address; collect failures whose hint differs (so we
        # can retry just those with the camp-name fallback).
        retries: list[tuple[int, str]] = []
        for i, (addr, hint) in enumerate(pairs):
            rec = primary[i] if primary and i < len(primary) else None
            point = _record_to_point(rec)
            out[addr] = point
            if point is None and hint and hint != addr:
                retries.append((i, hint))

        if retries:
            retry_recs = _run_async_blocking(
                self._spawn_batch([h for _, h in retries])
            )
            for j, (idx, _hint) in enumerate(retries):
                rec = retry_recs[j] if retry_recs and j < len(retry_recs) else None
                point = _record_to_point(rec)
                if point is not None:
                    addr = pairs[idx][0]
                    out[addr] = point
        return out

    async def _spawn_batch(self, queries: list[str]) -> list[Optional[dict]]:
        """Run ``etago --geocode --batch`` over the given queries.

        Returns a list aligned with input order. Entries are either the
        decoded NDJSON record or None when the line couldn't be parsed.
        """
        if not queries:
            return []
        cmd = [
            self.bin_path,
            "--geocode", "--batch",
            "--workers", str(self.batch_workers),
            "--per-timeout", f"{int(self.per_query_timeout_s)}s",
            "--timeout", f"{int(self.batch_total_timeout_s)}s",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError):
            return [None] * len(queries)
        stdin_blob = ("\n".join(queries) + "\n").encode("utf-8")
        try:
            stdout, _stderr = await asyncio.wait_for(
                proc.communicate(stdin_blob),
                timeout=self.batch_total_timeout_s + 5,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return [None] * len(queries)
        # rc=3 means "every line failed" — output is still valid NDJSON
        # (one error record per input). rc=2 is input error (shouldn't
        # happen with our shape) → nothing to parse.
        if proc.returncode == 2:
            return [None] * len(queries)
        return _parse_ndjson(stdout, expected=len(queries))


def _record_to_point(rec: Optional[dict]) -> Optional[GeoPoint]:
    if not rec or rec.get("error"):
        return None
    try:
        lat = float(rec["lat"])
        lon = float(rec["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    try:
        return GeoPoint(lat=lat, lon=lon)
    except Exception:
        return None


def _parse_ndjson(blob: bytes, *, expected: int) -> list[Optional[dict]]:
    """Decode NDJSON from etago --batch. Pads to `expected` length on parse error."""
    out: list[Optional[dict]] = []
    text = blob.decode("utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            out.append(None)
    while len(out) < expected:
        out.append(None)
    return out[:expected]


def _run_async_blocking(coro):
    """Run ``coro`` even when called from inside an event loop.

    asyncio.run() raises RuntimeError when nested (FastAPI handlers, async
    tests, etc). When that happens we delegate to a worker thread that owns
    its own event loop. Coroutines are single-use, so we detect "are we in
    a running loop?" *before* awaiting them — get_running_loop() is the
    one safe sniff that doesn't consume the coro.
    """
    in_loop = False
    try:
        asyncio.get_running_loop()
        in_loop = True
    except RuntimeError:
        in_loop = False

    if not in_loop:
        return asyncio.run(coro)

    out: dict = {}

    def runner():
        try:
            out["v"] = asyncio.run(coro)
        except Exception as e:  # pragma: no cover
            out["e"] = e

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join()
    return out.get("v")
