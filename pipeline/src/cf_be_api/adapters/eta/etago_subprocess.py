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

    # Chunking knobs — etago is fast at fanning N goroutines per process,
    # but a single Go-process serializes some bookkeeping (NDJSON write,
    # stdin scanner, signal handling). Splitting a large batch into K
    # parallel subprocesses raises the effective in-flight count to
    # K × workers without hitting any single process's GC/scheduling
    # ceiling. K=4 with workers=8 → 32 concurrent external requests, well
    # below per-IP rate-limit thresholds for Naver/Kakao but enough to
    # saturate typical broadband.
    chunk_size: int = 100
    parallel_chunks: int = 4

    def drive_eta_batch(
        self,
        origin: str,
        dests: Iterable[tuple[str, str]],
        *,
        concurrency: int = 4,
        timeout_s: float = 12.0,
    ) -> dict[str, EtaResult]:
        """Resolve N (camp_id, place) pairs across K parallel etago subprocesses.

        Layered parallelism — Python side spawns up to `parallel_chunks`
        subprocesses concurrently via asyncio.gather; each subprocess
        runs `--batch --workers concurrency` so it fans `concurrency`
        goroutines internally. Effective in-flight HTTP request count is
        ≈ parallel_chunks × concurrency. With the defaults that's 32, well
        below per-IP rate-limit thresholds for Naver/Kakao but enough to
        saturate typical broadband.

        Stdin format: TSV `origin\\tdest` per line.
        Stdout: NDJSON `{"start","end","duration_min"|"error","source"}`
        in input order. We zip the NDJSON back to the input id list.
        """
        pairs = list(dests)
        if not pairs:
            return {}
        # Total wall-clock budget: per-call timeout × per-chunk size,
        # capped at 10 minutes so a runaway batch doesn't hang the request.
        chunk_total_timeout_s = min(
            600.0, timeout_s + max(60.0, self.chunk_size * 0.4),
        )
        return asyncio.run(self._drive_eta_batch_chunked(
            origin, pairs, concurrency=concurrency,
            per_timeout_s=timeout_s, total_timeout_s=chunk_total_timeout_s,
        ))

    async def _drive_eta_batch_chunked(
        self, origin: str, pairs: list[tuple[str, str]], *,
        concurrency: int, per_timeout_s: float, total_timeout_s: float,
    ) -> dict[str, EtaResult]:
        # Split into roughly-equal chunks of at most `chunk_size`. With
        # chunk_size=100 the parallelism kicks in past 100 pairs; smaller
        # batches stay in a single subprocess (no overhead).
        cs = max(1, self.chunk_size)
        chunks = [pairs[i:i + cs] for i in range(0, len(pairs), cs)]
        # Cap concurrent subprocesses to parallel_chunks. asyncio.Semaphore
        # gates the gather — chunks beyond the cap wait for a free slot.
        sem = asyncio.Semaphore(max(1, self.parallel_chunks))

        async def _run_one(chunk: list[tuple[str, str]]) -> dict[str, EtaResult]:
            async with sem:
                return await self._spawn_drive_batch(
                    origin, chunk,
                    concurrency=concurrency,
                    per_timeout_s=per_timeout_s,
                    total_timeout_s=total_timeout_s,
                )

        # asyncio.gather fans out the chunks; each yields a dict, which
        # we flatten into one combined result map.
        partial = await asyncio.gather(*(_run_one(c) for c in chunks))
        merged: dict[str, EtaResult] = {}
        for piece in partial:
            merged.update(piece)
        return merged

    async def _spawn_drive_batch(
        self, origin: str, pairs: list[tuple[str, str]], *,
        concurrency: int, per_timeout_s: float, total_timeout_s: float,
    ) -> dict[str, EtaResult]:
        cmd = [
            self.bin_path, "--batch", "--json",
            "--workers", str(max(1, concurrency)),
            "--per-timeout", f"{int(per_timeout_s)}s",
            "--timeout", f"{int(total_timeout_s)}s",
        ]
        # Build stdin payload — every line is `origin<TAB>dest`. The
        # camp_id-to-place mapping is preserved by line-order: line N maps
        # to pairs[N], so output line N maps back to pairs[N][0].
        stdin_payload = "\n".join(
            f"{origin}\t{dest}" for _id, dest in pairs
        ).encode("utf-8") + b"\n"

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError) as e:
            err = f"spawn: {e}"
            return {pid: EtaResult(origin=origin, dest=dest, minutes=None, error=err)
                    for pid, dest in pairs}

        try:
            stdout, _stderr = await asyncio.wait_for(
                proc.communicate(input=stdin_payload),
                timeout=total_timeout_s + 5,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            err = f"timeout after {total_timeout_s:.0f}s"
            return {pid: EtaResult(origin=origin, dest=dest, minutes=None, error=err)
                    for pid, dest in pairs}

        # NDJSON one record per input line. Exit 3 = no successes; we still
        # parse stdout because every line carries either duration or error.
        lines = [ln for ln in stdout.decode("utf-8", errors="replace").splitlines() if ln.strip()]
        out: dict[str, EtaResult] = {}
        for (pid, dest), line in zip(pairs, lines):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                out[pid] = EtaResult(origin=origin, dest=dest, minutes=None, error="parse")
                continue
            if "duration_min" in payload:
                out[pid] = EtaResult(
                    origin=str(payload.get("start", origin)),
                    dest=str(payload.get("end", dest)),
                    minutes=int(payload["duration_min"]),
                    source=payload.get("source"),
                )
            else:
                out[pid] = EtaResult(
                    origin=origin, dest=dest, minutes=None,
                    error=str(payload.get("error", "unknown"))[:200],
                )
        # Stragglers — if the binary printed fewer lines than inputs (rare;
        # only on protocol failure), tag the rest as error so the caller
        # always gets one entry per input id.
        for pid, dest in pairs[len(lines):]:
            out[pid] = EtaResult(origin=origin, dest=dest, minutes=None, error="missing")
        return out
