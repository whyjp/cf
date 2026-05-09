"""Deterministic mock clusterer — assigns ids to clusters mod 3."""
from __future__ import annotations
import numpy as np


class MockClusterer:
    def cluster(self, ids: list[str], vectors: np.ndarray) -> dict[str, int]:
        return {cid: i % 3 for i, cid in enumerate(ids)}

    def label_cluster(self, cluster_id: int, member_ids: list[str],
                       member_concepts: dict[str, list[str]]) -> str:
        return f"mock-theme-{cluster_id}"
