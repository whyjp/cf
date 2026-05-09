"""HDBSCAN clusterer adapter — density-based clustering for theme discovery.

Implements ports.extract.ThemeClusterer.
"""
from __future__ import annotations
from collections import Counter
import numpy as np


class HdbscanClusterer:
    def __init__(self, min_cluster_size: int = 8, min_samples: int = 3):
        from sklearn.cluster import HDBSCAN
        self._H = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric="euclidean",
        )

    def cluster(self, ids: list[str], vectors: np.ndarray) -> dict[str, int]:
        if len(ids) == 0:
            return {}
        labels = self._H.fit_predict(vectors)
        return dict(zip(ids, labels.tolist()))

    def label_cluster(self, cluster_id: int, member_ids: list[str],
                       member_concepts: dict[str, list[str]]) -> str:
        c: Counter = Counter()
        for mid in member_ids:
            for k in (member_concepts.get(mid, []) or [])[:5]:
                c[k] += 1
        top = [k for k, _ in c.most_common(3)]
        return " · ".join(top) if top else f"theme-{cluster_id}"
