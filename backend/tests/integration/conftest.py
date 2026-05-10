"""Integration tests fixtures — run against the live docker stack.

Marker: @pytest.mark.integration. Skipped by default. Run via:
    pytest -m integration -v

Requires:
  - PostgreSQL at localhost:5432 (docker compose up)
  - FalkorDB at localhost:6379
  - PG already populated by `python -m cf_backend.cli pipeline run-all`
"""
from __future__ import annotations
import pytest

from cf_backend.settings import Settings
from cf_backend.container import Container


def pytest_collection_modifyitems(config, items):
    if config.getoption("-m", default=""):
        return  # user explicitly asked for a marker
    skip_integration = pytest.mark.skip(reason="integration tests skipped by default; run with -m integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(scope="session")
def container():
    s = Settings(embedder="mock")  # mock embedder is fine for read tests; ko-sroberta would also work
    c = Container(s)
    yield c
    c.close()
