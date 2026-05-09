"""Deterministic mock ETA provider for tests."""
from __future__ import annotations
from typing import Iterable
from ...domain.models import EtaResult


class MockEtaProvider:
    """Returns minutes = sum(len(origin), len(dest)) — deterministic per pair."""

    def drive_eta(self, origin: str, dest: str, *, timeout_s: float = 12.0) -> EtaResult:
        return EtaResult(origin=origin, dest=dest, minutes=len(origin) + len(dest), source="mock")

    def drive_eta_batch(
        self,
        origin: str,
        dests: Iterable[tuple[str, str]],
        *,
        concurrency: int = 4,
        timeout_s: float = 12.0,
    ) -> dict[str, EtaResult]:
        return {id_: self.drive_eta(origin, place) for id_, place in dests}
