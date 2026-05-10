from cf_backend.adapters.embed.mock import MockEmbedder
from cf_backend.adapters.extract.mock import MockConceptExtractor
from cf_backend.domain.models import Camp, Region, Concept
from cf_backend.usecases.extract_desc_signals import ExtractDescSignals


class FakeReader:
    def __init__(self, camps): self._c = camps
    def iter_all(self): return iter(self._c)
    def get(self, i): return next((c for c in self._c if c.id == i), None)
    def list_filtered(self, **kw): return self._c
    def count(self): return len(self._c)


class FakeReviewReader:
    def top_for(self, cid, n=3, sort="score"): return []
    def total_for(self, cid): return 0
    def iter_for(self, cid): return iter([])


class FakeDescWriter:
    def __init__(self): self.upserts = []; self.resets = []
    def upsert(self, camp_id, concept_id, score):
        self.upserts.append((camp_id, concept_id, score))
    def reset_for(self, camp_id):
        self.resets.append(camp_id)


def test_extract_desc_signals_writes_per_camp():
    camps = [
        Camp(id="c1", name="X1", region=Region(sido="강원", sigungu="평창군"),
             brief="키즈캠핑이 좋은 곳"),
        Camp(id="c2", name="X2", region=Region(sido="경기", sigungu="가평군"),
             brief="계곡과 트램펄린이 있어요"),
    ]
    vocab = [
        Concept(id="kids", name="키즈캠핑", source="manual"),
        Concept(id="valley", name="계곡", source="manual"),
        Concept(id="trampoline", name="트램펄린", source="manual"),
    ]
    writer = FakeDescWriter()
    uc = ExtractDescSignals(
        FakeReader(camps), FakeReviewReader(),
        MockEmbedder(), MockConceptExtractor(vocab), writer,
    )
    n = uc.execute(top_k=5, min_score=0.4)
    assert n >= 2
    assert "c1" in writer.resets and "c2" in writer.resets
    by_camp = {}
    for cid, kid, score in writer.upserts:
        by_camp.setdefault(cid, []).append(kid)
    assert "kids" in by_camp.get("c1", [])
    assert "valley" in by_camp.get("c2", [])


def test_extract_desc_signals_zero_camps():
    uc = ExtractDescSignals(FakeReader([]), FakeReviewReader(), MockEmbedder(),
                            MockConceptExtractor([]), FakeDescWriter())
    assert uc.execute() == 0
