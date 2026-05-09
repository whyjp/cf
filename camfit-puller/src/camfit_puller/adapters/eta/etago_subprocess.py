"""etago subprocess adapter — implements ports.eta.EtaProvider via the etago Go CLI."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Iterable, Optional

from ...domain.models import EtaResult
from ..etago_bin import resolve_etago_bin, EtagoUnavailable  # re-exported


__all__ = ["EtagoSubprocessProvider", "EtagoUnavailable"]


@dataclass
class EtagoSubprocessProvider:
    # Empty default — __post_init__ resolves (and auto-builds) on first use.
    bin_path: str = ""
    default_timeout_s: float = 12.0

    def __post_init__(self) -> None:
        if not self.bin_path:
            self.bin_path = resolve_etago_bin()

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
