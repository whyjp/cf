from __future__ import annotations
from typing import Protocol, runtime_checkable
import numpy as np
from ..domain.models import Concept


@runtime_checkable
class ConceptExtractor(Protocol):
    def vocabulary(self) -> list[Concept]: ...
    def extract(self, text: str, vector: np.ndarray | None = None,
                top_k: int = 10, min_score: float = 0.3) -> list[tuple[str, float]]: ...


@runtime_checkable
class NegationAwareExtractor(Protocol):
    def extract_with_polarity(self, text: str) -> list[tuple[str, int, str]]:
        """[(concept_id, +1 or -1, evidence_snippet), ...]"""
        ...


@runtime_checkable
class ThemeClusterer(Protocol):
    def cluster(self, ids: list[str], vectors: np.ndarray) -> dict[str, int]: ...
    def label_cluster(self, cluster_id: int, member_ids: list[str],
                       member_concepts: dict[str, list[str]]) -> str: ...
