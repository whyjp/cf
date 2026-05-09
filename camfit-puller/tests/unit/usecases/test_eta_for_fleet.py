from camfit_puller.adapters.eta.mock import MockEtaProvider
from camfit_puller.domain.models import Camp, Region
from camfit_puller.usecases.eta_for_fleet import EtaForFleet


class FakeReader:
    def __init__(self, camps): self._c = {c.id: c for c in camps}
    def iter_all(self): return iter(self._c.values())
    def get(self, i): return self._c.get(i)
    def list_filtered(self, *, ids=None, **kw):
        return [self._c[i] for i in (ids or list(self._c.keys())) if i in self._c]
    def count(self): return len(self._c)


def test_eta_for_fleet_returns_minutes_for_each_id():
    camps = [
        Camp(id="c1", name="A", region=Region(sido="강원", sigungu="평창군")),
        Camp(id="c2", name="B", region=Region(sido="경기", sigungu="가평군")),
    ]
    out = EtaForFleet(FakeReader(camps), MockEtaProvider()).execute(
        "서울역", ["c1", "c2"]
    )
    assert out["origin"] == "서울역"
    assert out["checked"] == 2
    assert out["within_count"] == 2  # max_minutes=None → all within
    assert all(r["minutes"] is not None for r in out["results"])


def test_eta_for_fleet_respects_max_minutes():
    camps = [Camp(id="c1", name="A", region=Region(sido="강원", sigungu="평창군"))]
    out = EtaForFleet(FakeReader(camps), MockEtaProvider()).execute(
        "S", ["c1"], max_minutes=2  # mock returns len("S")+len(place)
    )
    assert out["within_count"] == 0  # mock minutes will exceed 2
    assert out["results"][0]["within"] is False


def test_eta_for_fleet_unknown_id_returns_no_place():
    out = EtaForFleet(FakeReader([]), MockEtaProvider()).execute(
        "서울역", ["unknown"]
    )
    assert out["checked"] == 1
    assert out["results"][0]["minutes"] is None
    assert out["results"][0]["error"] == "no place name"
