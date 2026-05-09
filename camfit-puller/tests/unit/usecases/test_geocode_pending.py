from camfit_puller.adapters.geocode.mock import MockGeocoder
from camfit_puller.domain.models import Camp, GeoPoint, Region
from camfit_puller.usecases.geocode_pending import GeocodePending


class FakeReader:
    def __init__(self, camps): self._c = camps
    def iter_all(self): return iter(self._c)
    def get(self, i): return next((c for c in self._c if c.id == i), None)
    def list_filtered(self, **kw): return self._c
    def count(self): return len(self._c)


class FakeWriter:
    def __init__(self): self.geo_calls: list[tuple[str, float, float]] = []
    def upsert_many(self, *_): return 0
    def set_geo(self, camp_id, lat, lon):
        self.geo_calls.append((camp_id, lat, lon))
    def delete(self, *_): return False


def test_geocode_skips_camps_with_existing_geo():
    camps = [
        Camp(id="c1", name="A", region=Region(sido="강원", sigungu="평창군"),
             address="강원 평창군 진부면",
             geo=GeoPoint(lat=37.5, lon=128.5)),  # already geocoded
        Camp(id="c2", name="B", region=Region(sido="경기", sigungu="가평군"),
             address="경기 가평군"),  # missing
    ]
    writer = FakeWriter()
    out = GeocodePending(FakeReader(camps), writer, MockGeocoder()).execute()
    assert out["attempted"] == 1  # only c2
    assert out["resolved"] == 1
    assert out["failed"] == 0
    assert writer.geo_calls == [("c2", 37.5, 127.0)]


def test_geocode_uses_region_when_address_missing():
    camps = [Camp(id="c1", name="A",
                  region=Region(sido="강원", sigungu="평창군"))]
    # No address, no geo → uses sido+sigungu
    writer = FakeWriter()
    out = GeocodePending(FakeReader(camps), writer, MockGeocoder()).execute()
    assert out["resolved"] == 1
    assert writer.geo_calls[0][0] == "c1"


def test_geocode_failed_lookup_no_write():
    """Geocoder returning None → camp stays without coords (no fallback)."""
    class FailGeocoder:
        def lookup(self, *_, **__): return None
    camps = [Camp(id="c1", name="A",
                  region=Region(sido="강원", sigungu="평창군"),
                  address="가짜주소")]
    writer = FakeWriter()
    out = GeocodePending(FakeReader(camps), writer, FailGeocoder()).execute()
    assert out["attempted"] == 1
    assert out["resolved"] == 0
    assert out["failed"] == 1
    assert writer.geo_calls == []
