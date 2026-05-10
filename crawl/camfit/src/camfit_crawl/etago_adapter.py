"""etago subprocess adapter — drive-time ETA between Korean place names.

Wraps the existing `etago(.exe)` Go CLI (sibling project at ../etago) into an
async-friendly batch interface so the API can compute travel-time filters for
many camps in parallel.

Resolution order for the binary path:
    1. ``$ETAGO_BIN`` env var (explicit override).
    2. ``etago`` on PATH (`shutil.which`).
    3. Sibling repo: ``<repo-root>/etago/etago.exe`` (Windows) or ``etago/etago``.
    4. Raise :class:`EtagoUnavailable`.

etago's input layer rejects coordinates — pass place-name strings only
(e.g. ``"강남역"``, ``"평창 진부면"``). Reverse-geocoding from lat/lon is the
caller's responsibility.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT_GUESS = _THIS_DIR.parents[2]  # camfit-puller/src/camfit_puller → ../../..


def _resolve_bin() -> Optional[str]:
    explicit = os.environ.get("ETAGO_BIN")
    if explicit and Path(explicit).exists():
        return explicit
    on_path = shutil.which("etago")
    if on_path:
        return on_path
    for cand in (
        _REPO_ROOT_GUESS / "etago" / "etago.exe",
        _REPO_ROOT_GUESS / "etago" / "etago",
    ):
        if cand.exists():
            return str(cand)
    return None


class EtagoUnavailable(RuntimeError):
    """Raised when the etago binary cannot be located."""


@dataclass
class EtaResult:
    start: str
    end: str
    minutes: Optional[int]
    source: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "minutes": self.minutes,
            "source": self.source,
            "error": self.error,
        }


@dataclass
class EtagoClient:
    bin_path: str = field(default_factory=lambda: _resolve_bin() or "")
    default_timeout_s: float = 12.0
    cache: dict[tuple[str, str], EtaResult] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.bin_path:
            raise EtagoUnavailable(
                "etago binary not found. Set $ETAGO_BIN or build "
                "<repo>/etago (`go build -o etago.exe ./cmd/etago`)."
            )

    async def fetch(self, start: str, end: str, timeout_s: Optional[float] = None) -> EtaResult:
        key = (start, end)
        if key in self.cache:
            return self.cache[key]

        timeout = timeout_s or self.default_timeout_s
        # etago expects a Go duration string for --timeout (e.g. 12s).
        cmd = [self.bin_path, "--json", "--timeout", f"{int(timeout)}s", start, end]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError) as e:
            r = EtaResult(start=start, end=end, minutes=None, error=f"spawn: {e}")
            self.cache[key] = r
            return r

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout + 3)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            r = EtaResult(start=start, end=end, minutes=None, error="timeout")
            self.cache[key] = r
            return r

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            r = EtaResult(start=start, end=end, minutes=None, error=err[:200] or f"exit {proc.returncode}")
            self.cache[key] = r
            return r

        try:
            payload = json.loads(stdout.decode("utf-8"))
            r = EtaResult(
                start=str(payload.get("start", start)),
                end=str(payload.get("end", end)),
                minutes=int(payload["duration_min"]),
                source=payload.get("source"),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            r = EtaResult(start=start, end=end, minutes=None, error=f"parse: {e}")
        self.cache[key] = r
        return r

    async def fetch_many(
        self,
        origin: str,
        destinations: Iterable[tuple[str, str]],
        concurrency: int = 4,
        timeout_s: Optional[float] = None,
    ) -> dict[str, EtaResult]:
        """destinations = iterable of (id, place_name). Returns id→EtaResult."""
        sem = asyncio.Semaphore(max(1, concurrency))
        out: dict[str, EtaResult] = {}

        async def one(id_: str, place: str) -> None:
            async with sem:
                out[id_] = await self.fetch(origin, place, timeout_s)

        await asyncio.gather(*(one(i, p) for i, p in destinations))
        return out

    def clear_cache(self) -> None:
        self.cache.clear()
