"""Use-case: cluster all camp embeddings into emergent themes.

Pipeline:
  1. Load every camp's embedding from VectorIndex.get(camp_id).
  2. Cluster via ThemeClusterer.cluster(ids, vectors).
  3. For each non-noise cluster, label via clusterer.label_cluster(...) using
     member camps' top concepts (from ConceptRepository.for_camp).
  4. Theme.replace_all([...]) — idempotent wipe+insert.
  5. Per-camp Theme.assign(camp_id, theme_id).

Cluster id `-1` from HDBSCAN means noise (camp doesn't fit any theme).
Such camps get no theme assignment (no theme membership row).
"""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np

from ..domain.models import Theme
from ..ports.repo import CampReader, ConceptRepository, ThemeRepository
from ..ports.vector import VectorIndex
from ..ports.extract import ThemeClusterer


@dataclass
class DiscoverThemes:
    camp_reader: CampReader
    vector_index: VectorIndex
    clusterer: ThemeClusterer
    theme_repo: ThemeRepository
    concept_repo: ConceptRepository

    def execute(self) -> int:
        ids: list[str] = []
        vecs: list[np.ndarray] = []
        for camp in self.camp_reader.iter_all():
            v = self.vector_index.get(camp.id)
            if v is not None:
                ids.append(camp.id)
                vecs.append(v)
        if not ids:
            return 0
        labels_by_id = self.clusterer.cluster(ids, np.stack(vecs))
        # Per-camp concept ids for labeling
        member_concepts: dict[str, list[str]] = {}
        for cid in ids:
            ccs = self.concept_repo.for_camp(cid)
            # Concepts with positive aggregated score → camp's signal "members"
            member_concepts[cid] = [
                cc.concept_id for cc in ccs if cc.score > 0
            ]
        # Group by cluster, skip noise (-1)
        groups: dict[int, list[str]] = {}
        for cid, lbl in labels_by_id.items():
            if lbl < 0:
                continue
            groups.setdefault(lbl, []).append(cid)
        # Build Theme objects with derived labels
        themes: list[Theme] = []
        assignments: list[tuple[str, str]] = []
        for cluster_id, members in sorted(groups.items()):
            tid = f"t-{cluster_id:03d}"
            label = self.clusterer.label_cluster(cluster_id, members, member_concepts)
            themes.append(Theme(id=tid, label=label, member_count=len(members)))
            for mid in members:
                assignments.append((mid, tid))
        self.theme_repo.replace_all(themes)
        for cid, tid in assignments:
            self.theme_repo.assign(cid, tid)
        return len(themes)
