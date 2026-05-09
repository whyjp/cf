import numpy as np
import pytest
from camfit_puller.adapters.postgres.pool import PostgresPool
from camfit_puller.adapters.postgres.camp_repo import PostgresCampWriter
from camfit_puller.adapters.pgvector.index import PgvectorIndex
from camfit_puller.domain.models import Camp, Region


@pytest.fixture(scope="module")
def pool():
    p = PostgresPool("postgresql://camfit:camfit@localhost:5432/camfit")
    yield p
    p.close()


@pytest.fixture
def index(pool):
    return PgvectorIndex(pool, dim=768)


@pytest.fixture(autouse=True)
def setup(pool):
    """Seed 3 test camps so FK constraint allows embedding inserts."""
    w = PostgresCampWriter(pool)
    w.upsert_many([
        Camp(id="V_A", name="A", region=Region(sido="강원", sigungu="평창군")),
        Camp(id="V_B", name="B", region=Region(sido="경기", sigungu="가평군")),
        Camp(id="V_C", name="C", region=Region(sido="제주", sigungu="제주시")),
    ])
    yield
    with pool.conn() as c, c.cursor() as cur:
        cur.execute("DELETE FROM camp_embeddings WHERE camp_id LIKE 'V_%'")
        cur.execute("DELETE FROM camps WHERE id LIKE 'V_%'")


def test_upsert_then_knn_orders_by_similarity(index):
    rng = np.random.default_rng(42)
    a = rng.normal(size=768).astype(np.float32)
    b = a + rng.normal(scale=0.05, size=768).astype(np.float32)  # close to a
    c = rng.normal(size=768).astype(np.float32)                  # far from a
    index.upsert_many([("V_A", a, "h1"), ("V_B", b, "h2"), ("V_C", c, "h3")])
    hits = index.knn(a, k=2)
    assert hits[0][0] == "V_A"
    assert hits[1][0] == "V_B"


def test_size_and_reset(index):
    rng = np.random.default_rng(0)
    v = rng.normal(size=768).astype(np.float32)
    index.upsert_many([("V_A", v, "h"), ("V_B", v, "h"), ("V_C", v, "h")])
    assert index.size() >= 3
    index.reset()
    assert index.size() == 0


def test_filter_ids_restricts_search(index):
    rng = np.random.default_rng(7)
    a = rng.normal(size=768).astype(np.float32)
    index.upsert_many([("V_A", a, "h"), ("V_B", a, "h"), ("V_C", a, "h")])
    hits = index.knn(a, k=5, filter_ids={"V_B", "V_C"})
    ids = {x for x, _ in hits}
    assert ids <= {"V_B", "V_C"}
