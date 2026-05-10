from cf_be_api.domain.models import Camp, Region, Review
from cf_be_api.usecases.ingest_snapshot import IngestSnapshot


class FakeSource:
    name = "fake"
    def __init__(self, summaries, details, reviews_map, filters):
        self._sums = summaries
        self._dets = details
        self._revs = reviews_map
        self._filters = filters
    def iter_summaries(self): return iter(self._sums)
    def get_detail(self, cid): return self._dets.get(cid)
    def iter_reviews(self, cid, *, sort="recommend"):
        return iter(self._revs.get(cid, []))
    def iter_filters(self):
        return iter(self._filters)


class FakeCampWriter:
    def __init__(self): self.upserts = []
    def upsert_many(self, camps):
        n = 0
        for c in camps:
            self.upserts.append(c.id)
            n += 1
        return n
    def set_geo(self, *_a, **_k): pass
    def delete(self, *_a): return False


class FakeReviewWriter:
    def __init__(self): self.upserts = []
    def upsert_many(self, reviews):
        n = 0
        for r in reviews:
            self.upserts.append(r.id)
            n += 1
        return n


class FakeFilterRepo:
    def __init__(self): self.upserts = []
    def upsert(self, fid, name, kind, raw):
        self.upserts.append((fid, name, kind))
    def all(self): return self.upserts


def _camp(id_, **kw):
    base = dict(id=id_, name="x", region=Region(sido="강원", sigungu="평창군"))
    base.update(kw)
    return Camp(**base)


def test_ingest_walks_all_three_axes():
    sums = [_camp("a"), _camp("b")]
    dets = {"a": _camp("a", brief="A!"), "b": _camp("b", brief="B!")}
    revs = {"a": [Review(id="r1", camp_id="a", text="t1")],
            "b": [Review(id="r2", camp_id="b", text="t2"),
                  Review(id="r3", camp_id="b", text="t3")]}
    fts = [("F1", "필터1", "theme", None), ("F2", "필터2", "collection", {"k": "v"})]
    cw, rw, fr = FakeCampWriter(), FakeReviewWriter(), FakeFilterRepo()
    src = FakeSource(sums, dets, revs, fts)
    n_camps, n_reviews, n_filters = IngestSnapshot(src, cw, rw, fr).execute()
    assert n_camps == 2
    assert n_reviews == 3
    assert n_filters == 2
    assert cw.upserts == ["a", "b"]
    assert sorted(rw.upserts) == ["r1", "r2", "r3"]
    assert [f[0] for f in fr.upserts] == ["F1", "F2"]


def test_ingest_falls_back_to_summary_when_no_detail():
    sums = [_camp("only_sum")]
    dets = {}  # no details
    cw, rw, fr = FakeCampWriter(), FakeReviewWriter(), FakeFilterRepo()
    src = FakeSource(sums, dets, {}, [])
    n_c, n_r, n_f = IngestSnapshot(src, cw, rw, fr).execute()
    assert n_c == 1 and cw.upserts == ["only_sum"]


def test_ingest_zero_data_is_ok():
    src = FakeSource([], {}, {}, [])
    cw, rw, fr = FakeCampWriter(), FakeReviewWriter(), FakeFilterRepo()
    assert IngestSnapshot(src, cw, rw, fr).execute() == (0, 0, 0)
