import numpy as np
import pytest
from cf_be_api.adapters.postgres.pool import PostgresPool
from cf_be_api.adapters.postgres.camp_repo import PostgresCampWriter
from cf_be_api.adapters.pgvector.index import PgvectorIndex
from cf_be_api.adapters.numpy_vector.index import NumpyVectorIndex
from cf_be_api.domain.models import Camp, Region


@pytest.fixture(scope="module")
def pool():
    p = PostgresPool("postgresql://camfit:camfit@localhost:5432/camfit")
    yield p
    p.close()


def _seed_pg_camps(pool):
    """Ensure 3 test camps exist in PG so pgvector FK doesn't reject."""
    w = PostgresCampWriter(pool)
    w.upsert_many([
        Camp(id="V_A", name="A", region=Region(sido="강원", sigungu="평창군")),
        Camp(id="V_B", name="B", region=Region(sido="경기", sigungu="가평군")),
        Camp(id="V_C", name="C", region=Region(sido="제주", sigungu="제주시")),
    ])


def _cleanup_pg(pool):
    with pool.conn() as c, c.cursor() as cur:
        cur.execute("DELETE FROM camp_embeddings WHERE camp_id LIKE 'V_%'")
        cur.execute("DELETE FROM camps WHERE id LIKE 'V_%'")


@pytest.fixture
def index(request, pool):
    backend = request.param
    if backend == "pgvector":
        _seed_pg_camps(pool)
        idx = PgvectorIndex(pool, dim=768)
        yield idx
        _cleanup_pg(pool)
    elif backend == "numpy":
        idx = NumpyVectorIndex(dim=768)
        yield idx
        idx.reset()
    else:
        raise ValueError(f"unknown backend: {backend}")


_BACKENDS = pytest.mark.parametrize("index", ["pgvector", "numpy"], indirect=True)


@_BACKENDS
def test_upsert_then_knn_orders_by_similarity(index):
    rng = np.random.default_rng(42)
    a = rng.normal(size=768).astype(np.float32); a /= np.linalg.norm(a)
    b_noise = rng.normal(scale=0.05, size=768).astype(np.float32)
    b = a + b_noise; b /= np.linalg.norm(b)
    c = rng.normal(size=768).astype(np.float32); c /= np.linalg.norm(c)
    index.upsert_many([("V_A", a, "h1"), ("V_B", b, "h2"), ("V_C", c, "h3")])
    hits = index.knn(a, k=2)
    assert hits[0][0] == "V_A", f"expected V_A first, got {hits}"
    assert hits[1][0] == "V_B", f"expected V_B second, got {hits}"


@_BACKENDS
def test_size_and_reset(index):
    rng = np.random.default_rng(0)
    v = rng.normal(size=768).astype(np.float32); v /= np.linalg.norm(v)
    index.upsert_many([("V_A", v, "h"), ("V_B", v, "h"), ("V_C", v, "h")])
    assert index.size() >= 3
    index.reset()
    assert index.size() == 0


@_BACKENDS
def test_filter_ids_restricts_search(index):
    rng = np.random.default_rng(7)
    a = rng.normal(size=768).astype(np.float32); a /= np.linalg.norm(a)
    index.upsert_many([("V_A", a, "h"), ("V_B", a, "h"), ("V_C", a, "h")])
    hits = index.knn(a, k=5, filter_ids={"V_B", "V_C"})
    ids = {x for x, _ in hits}
    assert ids <= {"V_B", "V_C"}, f"filter breach: {ids}"
