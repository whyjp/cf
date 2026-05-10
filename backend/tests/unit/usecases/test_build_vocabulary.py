from cf_backend.domain.models import Camp, Region, Concept
from cf_backend.usecases.build_vocabulary import BuildVocabulary
from cf_backend.domain.concept_seeds import SEEDS


class FakeReader:
    def __init__(self, camps): self._c = camps
    def iter_all(self): return iter(self._c)
    def get(self, i): return next((c for c in self._c if c.id == i), None)
    def list_filtered(self, **kw): return self._c
    def count(self): return len(self._c)


class FakeConceptRepo:
    def __init__(self): self.seen: list[Concept] = []
    def upsert_concept(self, c: Concept): self.seen.append(c)
    def assign(self, *a, **kw): pass
    def for_camp(self, camp_id): return []
    def all(self): return list(self.seen)
    def find_by_name(self, name: str):
        for c in self.seen:
            if getattr(c, "name", None) == name:
                return c
        return None


def test_seeds_include_addendum_dimensions():
    """Per addendum: surface, view, space/parking, kids_facility concepts must be present."""
    ids = {sid for sid, *_ in SEEDS}
    # D1 surface
    assert "surface_gravel" in ids
    assert "surface_deck" in ids
    assert "surface_grass" in ids
    # D3 view (riverview/oceanview/mountainview baseline + lakeview/forestview added)
    assert "lakeview" in ids
    assert "forestview" in ids
    # D4 space + parking
    assert "space_generous" in ids
    assert "parking_on_site" in ids
    assert "parking_separate" in ids
    # D5 kids_facility
    assert "sandpit" in ids
    assert "animal_petting" in ids
    assert "kids_pool" in ids


def test_axis_concepts_marked_correctly():
    axis_ids = {sid for sid, _, _, is_axis in SEEDS if is_axis}
    # Per spec — primary axes for FE boolean toggles
    assert "kids" in axis_ids
    assert "pets" in axis_ids
    assert "valley" in axis_ids
    assert "trampoline" in axis_ids
    # Surface and parking are NOT axes (sub-filters)
    assert "surface_gravel" not in axis_ids
    assert "parking_on_site" not in axis_ids


def test_vocab_upserts_seeds_and_auto_derives_from_camps():
    """Camp hashtags + facilities should be auto-added beyond the seed list."""
    camps = [
        Camp(id="c1", name="X", region=Region(sido="강원", sigungu="평창군"),
             hashtags=["전혀새로운태그"], facilities=["전혀새로운시설"]),
    ]
    repo = FakeConceptRepo()
    n = BuildVocabulary(FakeReader(camps), repo).execute()
    names = {c.name for c in repo.seen}
    # Seeds present
    assert "키즈캠핑" in names
    assert "파쇄석" in names
    assert "별도 주차장" in names
    # Auto-derived
    assert "전혀새로운태그" in names
    assert "전혀새로운시설" in names
    # Returned count covers seeds + auto
    assert n >= len(SEEDS) + 2


def test_seed_sources_are_valid_literals():
    valid = {"hashtag", "facility", "manual", "ngram"}
    for sid, name, category, is_axis in SEEDS:
        assert isinstance(sid, str) and sid
        assert isinstance(name, str) and name
        assert isinstance(category, str) and category
        assert isinstance(is_axis, bool)
