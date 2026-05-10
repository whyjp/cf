import numpy as np
from cf_backend.adapters.cluster.mock import MockClusterer
from cf_backend.domain.models import Camp, Region, Theme, CampConcept
from cf_backend.usecases.discover_themes import DiscoverThemes


class FakeReader:
    def __init__(self, camps): self._c = camps
    def iter_all(self): return iter(self._c)
    def get(self, i): return next((c for c in self._c if c.id == i), None)
    def list_filtered(self, **kw): return self._c
    def count(self): return len(self._c)


class FakeIndex:
    def __init__(self, vecs): self._v = vecs
    @property
    def dim(self): return 768
    def upsert_many(self, *_): return 0
    def knn(self, *_, **__): return []
    def get(self, i): return self._v.get(i)
    def size(self): return len(self._v)
    def reset(self): self._v = {}


class FakeConceptRepo:
    def __init__(self, concepts_by_camp):
        self._d = concepts_by_camp
    def upsert_concept(self, *_): pass
    def assign(self, *_, **__): pass
    def for_camp(self, camp_id):
        return [CampConcept(camp_id=camp_id, concept_id=cid, score=1.0)
                for cid in self._d.get(camp_id, [])]
    def all(self): return []


class FakeThemeRepo:
    def __init__(self): self.replaced: list[Theme] = []; self.assignments: list = []
    def replace_all(self, themes): self.replaced = list(themes)
    def assign(self, camp_id, theme_id): self.assignments.append((camp_id, theme_id))
    def for_camp(self, camp_id): return None
    def all(self): return list(self.replaced)


def test_discover_themes_creates_groups():
    camps = [Camp(id=f"c{i}", name=str(i), region=Region(sido="x", sigungu="y"))
             for i in range(6)]
    rng = np.random.default_rng(0)
    vecs = {c.id: rng.normal(size=768).astype(np.float32) for c in camps}
    concept_repo = FakeConceptRepo({
        "c0": ["kids"], "c1": ["valley"], "c2": ["kids"],
        "c3": ["valley"], "c4": ["trampoline"], "c5": ["trampoline"],
    })
    theme_repo = FakeThemeRepo()
    uc = DiscoverThemes(
        FakeReader(camps), FakeIndex(vecs), MockClusterer(),
        theme_repo, concept_repo,
    )
    n = uc.execute()
    assert n >= 1
    # Mock clusterer assigns mod-3, so we expect 3 themes
    assert n == 3
    # All 6 camps assigned (no noise from mock)
    assert len(theme_repo.assignments) == 6
    # Theme labels follow MockClusterer.label_cluster pattern
    labels = {t.label for t in theme_repo.replaced}
    assert all(label.startswith("mock-theme-") for label in labels)


def test_discover_themes_zero_camps():
    uc = DiscoverThemes(FakeReader([]), FakeIndex({}), MockClusterer(),
                        FakeThemeRepo(), FakeConceptRepo({}))
    assert uc.execute() == 0


def test_discover_themes_skips_camps_without_embeddings():
    camps = [Camp(id="c0", name="0", region=Region(sido="x", sigungu="y")),
             Camp(id="c1", name="1", region=Region(sido="x", sigungu="y"))]
    # Only c0 has an embedding
    vecs = {"c0": np.zeros(768, dtype=np.float32)}
    theme_repo = FakeThemeRepo()
    uc = DiscoverThemes(FakeReader(camps), FakeIndex(vecs), MockClusterer(),
                        theme_repo, FakeConceptRepo({"c0": ["kids"]}))
    n = uc.execute()
    # Only c0 clustered → 1 theme
    assert n == 1
    assert theme_repo.assignments == [("c0", "t-000")]
