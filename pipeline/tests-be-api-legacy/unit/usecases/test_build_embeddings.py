import numpy as np
from cf_be_api.adapters.embed.mock import MockEmbedder
from cf_be_api.domain.models import Camp, Region
from cf_be_api.usecases.build_embeddings import BuildEmbeddings


class FakeReader:
    def __init__(self, camps): self._c = camps
    def iter_all(self): return iter(self._c)
    def get(self, i):
        for c in self._c:
            if c.id == i: return c
        return None
    def list_filtered(self, **kw): return self._c
    def count(self): return len(self._c)


class FakeReviewReader:
    def top_for(self, cid, n=3, sort="score"): return []
    def total_for(self, cid): return 0
    def iter_for(self, cid): return iter([])


class FakeIndex:
    dim = 768
    def __init__(self): self._d = {}
    def upsert_many(self, items):
        n = 0
        for cid, vec, *_ in items:
            self._d[cid] = vec
            n += 1
        return n
    def knn(self, q, k=10, filter_ids=None):
        return [(cid, float(np.dot(vec, q))) for cid, vec in self._d.items()][:k]
    def get(self, i): return self._d.get(i)
    def size(self): return len(self._d)
    def reset(self): self._d.clear()


def test_build_embeddings_writes_one_vector_per_camp():
    camps = [
        Camp(id=f"c{i}", name=f"C{i}",
             region=Region(sido="강원", sigungu="평창군"),
             brief=f"b{i}")
        for i in range(3)
    ]
    uc = BuildEmbeddings(FakeReader(camps), FakeReviewReader(), MockEmbedder(), FakeIndex())
    n = uc.execute()
    assert n == 3


def test_build_embeddings_zero_camps_returns_zero():
    uc = BuildEmbeddings(FakeReader([]), FakeReviewReader(), MockEmbedder(), FakeIndex())
    assert uc.execute() == 0


def test_build_embeddings_uses_text_hash():
    """text_hash is included in upsert tuples — verify by inspecting recorded items."""
    camps = [
        Camp(id="c1", name="C1", region=Region(sido="강원", sigungu="평창군"), brief="b1"),
    ]
    captured = []
    class CaptureIndex(FakeIndex):
        def upsert_many(self, items):
            for it in items:
                captured.append(it)
            return len(captured)
    uc = BuildEmbeddings(FakeReader(camps), FakeReviewReader(), MockEmbedder(), CaptureIndex())
    uc.execute()
    assert len(captured) == 1
    cid, vec, text_h = captured[0]
    assert cid == "c1"
    assert isinstance(vec, np.ndarray)
    assert isinstance(text_h, str) and len(text_h) == 64  # sha256 hex
