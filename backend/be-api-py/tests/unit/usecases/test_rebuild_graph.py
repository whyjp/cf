from cf_be_api.domain.models import Camp, Concept, Region, Theme, CampConcept
from cf_be_api.usecases.rebuild_graph import RebuildGraph


class FakeReader:
    def __init__(self, camps): self._c = camps
    def iter_all(self): return iter(self._c)
    def get(self, i): return next((c for c in self._c if c.id == i), None)
    def list_filtered(self, **kw): return self._c
    def count(self): return len(self._c)


class FakeConceptRepo:
    def __init__(self, concepts, by_camp):
        self._all = concepts
        self._by = by_camp
    def upsert_concept(self, *_): pass
    def assign(self, *_, **__): pass
    def for_camp(self, camp_id):
        return [CampConcept(camp_id=camp_id, concept_id=cid, score=score)
                for cid, score in self._by.get(camp_id, [])]
    def all(self): return list(self._all)


class FakeThemeRepo:
    def __init__(self, themes, by_camp):
        self._all = themes
        self._by = by_camp
    def replace_all(self, *_): pass
    def assign(self, *_): pass
    def for_camp(self, camp_id): return self._by.get(camp_id)
    def all(self): return list(self._all)


class FakeGraph:
    def __init__(self):
        self.queries: list[tuple[str, dict]] = []
        self.reset_calls = 0
    def query(self, cypher, params=None):
        self.queries.append((cypher, params or {}))
        return []
    def reset(self, graph_name=None):
        self.reset_calls += 1
    def healthcheck(self): return True


def test_rebuild_graph_resets_and_writes_camps_concepts_themes():
    camps = [
        Camp(id="c1", name="A", region=Region(sido="강원", sigungu="평창군"),
             types=["autoCamping"], hashtags=["계곡캠핑장"],
             collections=["테마:대형견과함께"]),
    ]
    concepts = [Concept(id="kids", name="키즈", source="manual"),
                Concept(id="pets", name="반려동반", source="manual")]
    by_camp_concepts = {"c1": [("pets", 1.0), ("kids", -0.5)]}  # only pets > 0 → edge
    themes = [Theme(id="t-000", label="견공", member_count=10)]
    by_camp_themes = {"c1": themes[0]}
    g = FakeGraph()
    uc = RebuildGraph(
        FakeReader(camps),
        FakeConceptRepo(concepts, by_camp_concepts),
        FakeThemeRepo(themes, by_camp_themes),
        g,
    )
    out = uc.execute()
    assert g.reset_calls == 1
    assert out["camps"] == 1
    assert out["concepts"] == 2
    assert out["themes"] == 1
    assert out["concept_edges"] == 1  # only pets (score>0); kids skipped
    assert out["theme_edges"] == 1


def test_rebuild_graph_zero_camps_only_resets():
    g = FakeGraph()
    RebuildGraph(
        FakeReader([]),
        FakeConceptRepo([], {}),
        FakeThemeRepo([], {}),
        g,
    ).execute()
    assert g.reset_calls == 1
    assert g.queries == []  # no nodes/edges to write


def test_rebuild_graph_skips_negative_concept_edges():
    camps = [Camp(id="c1", name="A", region=Region(sido="x", sigungu="y"))]
    by_camp_concepts = {"c1": [
        ("kids", 0.5),    # positive — edge
        ("pets", -0.3),   # negative — skipped
        ("noise", 0.0),   # zero — skipped
    ]}
    g = FakeGraph()
    out = RebuildGraph(
        FakeReader(camps),
        FakeConceptRepo([], by_camp_concepts),
        FakeThemeRepo([], {}),
        g,
    ).execute()
    assert out["concept_edges"] == 1
