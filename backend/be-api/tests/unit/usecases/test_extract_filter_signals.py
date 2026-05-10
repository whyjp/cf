from cf_be_api.domain.models import Camp, Region
from cf_be_api.usecases.extract_filter_signals import ExtractCamfitFilterSignals


class FakeReader:
    def __init__(self, camps): self._c = camps
    def iter_all(self): return iter(self._c)
    def get(self, i): return next((c for c in self._c if c.id == i), None)
    def list_filtered(self, **kw): return self._c
    def count(self): return len(self._c)


class FakeMappingRepo:
    def __init__(self, m): self._m = m  # {filter_id: [(concept_id, polarity), ...]}
    def upsert_mapping(self, *_): pass
    def for_filter(self, fid): return self._m.get(fid, [])


class FakeFilterSignalWriter:
    def __init__(self): self.rows = []; self.resets = []
    def upsert(self, camp_id, concept_id, score, evidence):
        self.rows.append((camp_id, concept_id, score, evidence))
    def reset_for(self, camp_id): self.resets.append(camp_id)


def test_filter_signals_emit_with_polarity():
    camps = [
        Camp(id="c1", name="A", region=Region(sido="강원", sigungu="평창군"),
             collections=["테마:대형견과함께", "키즈캠핑장"]),
        Camp(id="c2", name="B", region=Region(sido="경기", sigungu="가평군"),
             collections=["노키즈캠핑장"]),
    ]
    mapping = {
        "테마:대형견과함께": [("pets", 1)],
        "키즈캠핑장": [("kids", 1)],
        "노키즈캠핑장": [("kids", -1)],
    }
    writer = FakeFilterSignalWriter()
    uc = ExtractCamfitFilterSignals(FakeReader(camps), FakeMappingRepo(mapping), writer)
    n = uc.execute()
    assert n == 3
    by_camp_concept = {(c, k): (s, ev) for c, k, s, ev in writer.rows}
    assert by_camp_concept[("c1", "pets")][0] == 1.0
    assert by_camp_concept[("c1", "kids")][0] == 1.0
    assert by_camp_concept[("c2", "kids")][0] == -1.0


def test_filter_signals_unknown_filter_skipped():
    camps = [Camp(id="c1", name="A", region=Region(sido="강원", sigungu="평창군"),
                  collections=["unknown_filter"])]
    writer = FakeFilterSignalWriter()
    uc = ExtractCamfitFilterSignals(FakeReader(camps), FakeMappingRepo({}), writer)
    n = uc.execute()
    assert n == 0  # no mappings → no signals
    assert writer.resets == ["c1"]
