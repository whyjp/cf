"""Note: ComputeMarks uses concrete PostgresPool by design (PG-specific quantile
SQL). This is the same pragmatic exception used for RefreshAggregatedSignals.
For unit testing we use a thin in-process Postgres mock OR run against the
live PG and clean up afterwards. Here we use the live-PG approach (treated as
contract test, gated by pytest.mark.integration if you prefer)."""
import pytest
from camfit_puller.adapters.postgres.pool import PostgresPool
from camfit_puller.adapters.postgres.mark_repo import PostgresMarkRepo
from camfit_puller.usecases.compute_marks import ComputeMarks


@pytest.fixture(scope="module")
def pool():
    p = PostgresPool("postgresql://camfit:camfit@localhost:5432/camfit")
    yield p
    p.close()


def test_compute_marks_runs_without_error(pool):
    """Smoke: execute on live PG state. No assertion on counts -- just no error."""
    repo = PostgresMarkRepo(pool)
    out = ComputeMarks(pool, repo).execute()
    assert isinstance(out, dict)
    assert all(isinstance(v, int) for v in out.values())


def test_mark_repo_query_levels(pool):
    """Smoke: for_axis with min_level filter."""
    repo = PostgresMarkRepo(pool)
    # After a compute run, query each axis at exceptional level
    for axis in ("kids", "view", "facility"):
        marks = repo.for_axis(axis, min_level="exceptional", limit=5)
        assert isinstance(marks, list)
