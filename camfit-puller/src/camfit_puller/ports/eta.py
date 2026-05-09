from __future__ import annotations
from typing import Iterable, Protocol, runtime_checkable
from ..domain.models import EtaResult


@runtime_checkable
class EtaProvider(Protocol):
    def drive_eta(self, origin: str, dest: str, *, timeout_s: float = 12.0) -> EtaResult: ...
    def drive_eta_batch(self, origin: str, dests: Iterable[tuple[str, str]],
                         *, concurrency: int = 4, timeout_s: float = 12.0) -> dict[str, EtaResult]: ...
