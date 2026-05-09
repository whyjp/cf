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


def test_geocode_uses_batch_path_when_geocoder_supports_it():
    """When the geocoder exposes lookup_many, GeocodePending must use it
    instead of N lookup() calls — that's the whole reason etago has a
    batch mode (single subprocess vs spawn-per-camp)."""

    class BatchGeocoder:
        def __init__(self):
            self.batch_calls: list[list[tuple[str, str | None]]] = []
            self.lookup_calls = 0

        def lookup(self, *_, **__):
            self.lookup_calls += 1
            return None  # we should never reach here

        def lookup_many(self, items):
            pairs = list(items)
            self.batch_calls.append(pairs)
            # Resolve every odd-indexed input, fail the rest, to verify
            # the use-case writes only the resolved ones.
            out = {}
            for i, (addr, _hint) in enumerate(pairs):
                out[addr] = GeoPoint(lat=37.0 + i * 0.1, lon=127.0 + i * 0.1) if i % 2 == 1 else None
            return out

    camps = [
        Camp(id=f"c{i}", name=f"N{i}",
             region=Region(sido="강원", sigungu="평창군"),
             address=f"강원 평창군 진부면 {i}길")
        for i in range(4)
    ]
    g = BatchGeocoder()
    writer = FakeWriter()
    out = GeocodePending(FakeReader(camps), writer, g).execute()

    # One batch call, no per-item lookups.
    assert len(g.batch_calls) == 1
    assert g.lookup_calls == 0
    # 4 camps; odd indexes 1 and 3 resolve; 0 and 2 fail.
    assert out == {"attempted": 4, "resolved": 2, "failed": 2}
    # Writer only invoked for resolved camps.
    written_ids = sorted(c[0] for c in writer.geo_calls)
    assert written_ids == ["c1", "c3"]


def test_batch_path_collapses_duplicate_addresses_to_one_query_with_per_camp_writes():
    """Two camps sharing the exact same address (e.g. '1캠핑장 / 2캠핑장') must
    geocode in one query but each get the resolved coord written to PG."""

    class BatchGeocoder:
        def __init__(self):
            self.last_pairs: list[tuple[str, str | None]] = []

        def lookup(self, *_, **__):
            return None

        def lookup_many(self, items):
            self.last_pairs = list(items)
            return {addr: GeoPoint(lat=37.5, lon=128.0) for addr, _ in self.last_pairs}

    camps = [
        Camp(id="cA", name="원주두리 1캠핑장",
             region=Region(sido="강원", sigungu="원주시"),
             address="강원 원주시 신림면 황둔리 525"),
        Camp(id="cB", name="원주두리 2캠핑장",
             region=Region(sido="강원", sigungu="원주시"),
             address="강원 원주시 신림면 황둔리 525"),
    ]
    g = BatchGeocoder()
    writer = FakeWriter()
    out = GeocodePending(FakeReader(camps), writer, g).execute()

    # Single de-duplicated query upstream.
    assert len(g.last_pairs) == 1
    # But both camps got coords.
    assert out == {"attempted": 2, "resolved": 2, "failed": 0}
    assert sorted(c[0] for c in writer.geo_calls) == ["cA", "cB"]
