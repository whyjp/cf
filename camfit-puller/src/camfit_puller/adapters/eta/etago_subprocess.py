"""etago subprocess adapter — implements ports.eta.EtaProvider via the etago Go CLI."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from ...domain.models import EtaResult


_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT_GUESS = _THIS_DIR.parents[4]  # eta/ → adapters/ → camfit_puller/ → src/ → camfit-puller/ → cf root


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
class EtagoSubprocessProvider:
    bin_path: str = field(default_factory=lambda: _resolve_bin() or "")
    default_timeout_s: float = 12.0

    def __post_init__(self) -> None:
        if not self.bin_path:
            raise EtagoUnavailable(
                "etago binary not found. Set $ETAGO_BIN or build "
                "<repo>/etago (`go build -o etago.exe ./cmd/etago`)."
            )

    async def _fetch_one(self, origin: str, dest: str, timeout_s: float) -> EtaResult:
        cmd = [self.bin_path, "--json", "--timeout", f"{int(timeout_s)}s", origin, dest]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError) as e:
            return EtaResult(origin=origin, dest=dest, minutes=None, error=f"spawn: {e}")
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s + 3)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return EtaResult(origin=origin, dest=dest, minutes=None, error="timeout")
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            return EtaResult(
                origin=origin, dest=dest, minutes=None,
                error=err[:200] or f"exit {proc.returncode}",
            )
        try:
            payload = json.loads(stdout.decode("utf-8"))
            return EtaResult(
                origin=str(payload.get("start", origin)),
                dest=str(payload.get("end", dest)),
                minutes=int(payload["duration_min"]),
                source=payload.get("source"),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return EtaResult(origin=origin, dest=dest, minutes=None, error=f"parse: {e}")

    def drive_eta(self, origin: str, dest: str, *, timeout_s: float = 12.0) -> EtaResult:
        return asyncio.run(self._fetch_one(origin, dest, timeout_s))

    def drive_eta_batch(
        self,
        origin: str,
        dests: Iterable[tuple[str, str]],
        *,
        concurrency: int = 4,
        timeout_s: float = 12.0,
    ) -> dict[str, EtaResult]:
        async def _run() -> dict[str, EtaResult]:
            sem = asyncio.Semaphore(max(1, concurrency))
            out: dict[str, EtaResult] = {}

            async def one(id_: str, place: str) -> None:
                async with sem:
                    out[id_] = await self._fetch_one(origin, place, timeout_s)

            await asyncio.gather(*(one(i, p) for i, p in dests))
            return out

        return asyncio.run(_run())
