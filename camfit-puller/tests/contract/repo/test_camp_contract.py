import pytest
from camfit_puller.adapters.postgres.pool import PostgresPool
from camfit_puller.adapters.postgres.camp_repo import PostgresCampReader, PostgresCampWriter
from camfit_puller.domain.models import Camp, Region, GeoPoint


@pytest.fixture(scope="module")
def pool():
    p = PostgresPool("postgresql://camfit:camfit@localhost:5432/camfit")
    yield p
    p.close()


@pytest.fixture
def reader(pool):
    return PostgresCampReader(pool)


@pytest.fixture
def writer(pool):
    return PostgresCampWriter(pool)


@pytest.fixture(autouse=True)
def clean(pool):
    with pool.conn() as c, c.cursor() as cur:
        cur.execute("DELETE FROM camps WHERE id LIKE 'TEST_%'")
    yield
    with pool.conn() as c, c.cursor() as cur:
        cur.execute("DELETE FROM camps WHERE id LIKE 'TEST_%'")


def _mk(id_, **kw):
    base = dict(id=id_, name="t", region=Region(sido="강원", sigungu="평창군"))
    base.update(kw)
    return Camp(**base)


def test_upsert_then_get(writer, reader):
    n = writer.upsert_many([_mk("TEST_1", brief="bb")])
    assert n == 1
    out = reader.get("TEST_1")
    assert out is not None
    assert out.brief == "bb"


def test_upsert_replaces_relations(writer, reader):
    writer.upsert_many([_mk("TEST_2", types=["autoCamping"], hashtags=["a"])])
    writer.upsert_many([_mk("TEST_2", types=["pension"], hashtags=["b"])])
    out = reader.get("TEST_2")
    assert out.types == ["pension"]
    assert out.hashtags == ["b"]


def test_set_geo(writer, reader):
    writer.upsert_many([_mk("TEST_3")])
    writer.set_geo("TEST_3", 37.5, 127.0)
    out = reader.get("TEST_3")
    assert out.geo == GeoPoint(lat=37.5, lon=127.0)


def test_list_filtered_by_sido(writer, reader):
    writer.upsert_many([
        _mk("TEST_4", region=Region(sido="강원", sigungu="평창군")),
        _mk("TEST_5", region=Region(sido="경기", sigungu="가평군")),
    ])
    rows = reader.list_filtered(sido="강원")
    ids = {c.id for c in rows}
    assert "TEST_4" in ids and "TEST_5" not in ids
