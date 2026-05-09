"""Use-case: rebuild FalkorDB graph from PG truth.

Idempotent: wipes the graph then re-creates all nodes and edges. Safe to re-run
after any signal/concept/theme update.

Node schema (matches earlier work + parallel /graph viewer agent's expectations):
  Camp(id, name, lat, lon, url, address, description)
  Region(sido, sigungu)
  Category(name)         — from Camp.types
  Facility(name)         — from Camp.facilities + additional_facilities
  Hashtag(name)
  LocationType(name)
  Collection(name)       — camfit's native curation/theme membership
  Concept(id, name, source) — auto-derived from review/desc/filter
  Theme(id, label, count)  — emergent clusters

Edges:
  (Camp)-[:LOCATED_IN]->(Region)
  (Camp)-[:HAS_CATEGORY]->(Category)
  (Camp)-[:HAS_FACILITY]->(Facility)
  (Camp)-[:HAS_HASHTAG]->(Hashtag)
  (Camp)-[:HAS_LOCATION]->(LocationType)
  (Camp)-[:IN_COLLECTION]->(Collection)
  (Camp)-[:HAS_CONCEPT {score}]->(Concept)   — only when final_score > 0
  (Camp)-[:IN_THEME]->(Theme)
"""
from __future__ import annotations
from dataclasses import dataclass

from ..ports.repo import CampReader, ConceptRepository, ThemeRepository
from ..ports.graph import GraphStore


@dataclass
class RebuildGraph:
    camp_reader: CampReader
    concept_repo: ConceptRepository
    theme_repo: ThemeRepository
    graph: GraphStore

    def execute(self) -> dict:
        self.graph.reset()
        n_camps = 0
        for camp in self.camp_reader.iter_all():
            params = {
                "id": camp.id,
                "name": camp.name,
                "lat": camp.geo.lat if camp.geo else None,
                "lon": camp.geo.lon if camp.geo else None,
                "url": camp.url,
                "addr": camp.address,
                "desc": camp.description,
                "sido": camp.region.sido,
                "sigungu": camp.region.sigungu,
                "types": camp.types,
                "facs": list(set(camp.facilities + camp.additional_facilities)),
                "hashtags": camp.hashtags,
                "locs": camp.location_types,
                "cols": camp.collections,
            }
            self.graph.query(
                """
                MERGE (c:Camp {id:$id})
                SET c.name=$name, c.lat=$lat, c.lon=$lon, c.url=$url,
                    c.address=$addr, c.description=$desc
                MERGE (r:Region {sido:$sido, sigungu:$sigungu})
                MERGE (c)-[:LOCATED_IN]->(r)
                FOREACH (t IN $types | MERGE (cat:Category {name:t}) MERGE (c)-[:HAS_CATEGORY]->(cat))
                FOREACH (f IN $facs   | MERGE (ff:Facility {name:f}) MERGE (c)-[:HAS_FACILITY]->(ff))
                FOREACH (h IN $hashtags | MERGE (ht:Hashtag {name:h}) MERGE (c)-[:HAS_HASHTAG]->(ht))
                FOREACH (l IN $locs   | MERGE (lt:LocationType {name:l}) MERGE (c)-[:HAS_LOCATION]->(lt))
                FOREACH (k IN $cols   | MERGE (col:Collection {name:k}) MERGE (c)-[:IN_COLLECTION]->(col))
                """,
                params,
            )
            n_camps += 1

        # Concept and Theme nodes (derived signals)
        n_concepts = 0
        for concept in self.concept_repo.all():
            self.graph.query(
                "MERGE (k:Concept {id:$id}) SET k.name=$name, k.source=$src",
                {"id": concept.id, "name": concept.name, "src": concept.source},
            )
            n_concepts += 1

        n_themes = 0
        for theme in self.theme_repo.all():
            self.graph.query(
                "MERGE (t:Theme {id:$id}) SET t.label=$label, t.count=$n",
                {"id": theme.id, "label": theme.label, "n": theme.member_count},
            )
            n_themes += 1

        # Camp ↔ Concept (only positive aggregated scores)
        n_concept_edges = 0
        n_theme_edges = 0
        for camp in self.camp_reader.iter_all():
            for cc in self.concept_repo.for_camp(camp.id):
                if cc.score > 0:
                    self.graph.query(
                        """MATCH (c:Camp {id:$cid}), (k:Concept {id:$kid})
                           MERGE (c)-[r:HAS_CONCEPT]->(k) SET r.score=$s""",
                        {"cid": cc.camp_id, "kid": cc.concept_id, "s": float(cc.score)},
                    )
                    n_concept_edges += 1
            t = self.theme_repo.for_camp(camp.id)
            if t:
                self.graph.query(
                    """MATCH (c:Camp {id:$cid}), (t:Theme {id:$tid})
                       MERGE (c)-[:IN_THEME]->(t)""",
                    {"cid": camp.id, "tid": t.id},
                )
                n_theme_edges += 1

        return {
            "camps": n_camps,
            "concepts": n_concepts,
            "themes": n_themes,
            "concept_edges": n_concept_edges,
            "theme_edges": n_theme_edges,
        }
