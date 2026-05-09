from camfit_puller.adapters.embed.mock import MockEmbedder
from camfit_puller.domain.models import Camp, Region
from camfit_puller.usecases.semantic_search import SemanticSearch
import numpy as np


class FakeIndex:
    def __init__(self, vecs):
        self._v = vecs
    @property
    def dim(self): return 768
    def upsert_many(self, *_): return 0
    def knn(self, q, k=10, filter_ids=None):
        sims = [(cid, float(np.dot(v, q))) for cid, v in self._v.items()]
        return sorted(sims, key=lambda x: -x[1])[:k]
    def get(self, *_): return None
    def size(self): return len(self._v)
    def reset(self): self._v = {}


class FakeReader:
    def __init__(self, camps):
        self._c = {c.id: c for c in camps}
    def list_filtered(self, *, ids=None, **kw):
        return [self._c[i] for i in (ids or list(self._c.keys())) if i in self._c]
    def get(self, i): return self._c.get(i)
    def iter_all(self): return iter(self._c.values())
    def count(self): return len(self._c)


def test_semantic_search_returns_in_score_order():
    emb = MockEmbedder()
    camps = [Camp(id=f"c{i}", name=str(i), region=Region(sido="x", sigungu="y")) for i in range(3)]
    vecs = {c.id: emb.encode_one(c.name) for c in camps}
    uc = SemanticSearch(emb, FakeIndex(vecs), FakeReader(camps))
    out = uc.execute("0", k=3)
    assert out[0].id == "c0"


def test_semantic_search_empty_returns_empty():
    emb = MockEmbedder()
    uc = SemanticSearch(emb, FakeIndex({}), FakeReader([]))
    assert uc.execute("anything", k=10) == []


def test_semantic_search_preserves_knn_order():
    emb = MockEmbedder()
    camps = [Camp(id=f"c{i}", name=str(i), region=Region(sido="x", sigungu="y")) for i in range(5)]
    vecs = {c.id: emb.encode_one(c.name) for c in camps}
    uc = SemanticSearch(emb, FakeIndex(vecs), FakeReader(camps))
    # Search by query "2" — c2 should rank highest
    out = uc.execute("2", k=5)
    assert out[0].id == "c2"
    # Order from knn must be preserved end-to-end (not lost via reader's dict)
    knn_order = [cid for cid, _ in FakeIndex(vecs).knn(emb.encode_one("2"), k=5)]
    assert [c.id for c in out] == knn_order
