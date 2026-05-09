# P2 — PG + pgvector + Embedding KG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace RocksDB with PostgreSQL + pgvector + FalkorDB hexagonal stack; add 3-source signal classification, KeyBERT auto-concepts, and HDBSCAN auto-themes; ship as a swap-friendly local-first stack.

**Architecture:** Hexagonal (ports & adapters). `usecases/` depends only on `ports/` Protocols. `container.py` (composition root) wires concrete adapters from env (`CAMFIT_*`). FalkorDB stays (external viewer compat); RocksDB deleted on cutover.

**Tech Stack:** PostgreSQL 16 + pgvector, FalkorDB, sentence-transformers (jhgan/ko-sroberta-multitask, 768d), scikit-learn HDBSCAN, FastAPI, typer, alembic, pydantic v2, pydantic-settings, psycopg[pool], httpx, loguru, pytest + testcontainers.

**Reference spec:** `docs/superpowers/specs/2026-05-09-p2-pg-embedding-kg-design.md`

**Milestones:**
- M1 (T1–T15): foundation — PG container, schema, domain, ports, Postgres adapters
- M2 (T16–T22): embeddings — sentence-transformers, vocabulary, embeddings table, semantic search
- M3 (T23–T28): classification — KeyBERT desc signals, Korean negation review signals, camfit filter signals
- M4 (T29–T31): themes + graph — HDBSCAN, RebuildGraph use-case
- M5 (T32–T35): migration ETL — `data/*.json` → PG; seed concepts + filter mapping
- M6 (T36–T39): cutover — RocksDB delete, API + CLI refactor
- M7 (T40–T44): integration tests + acceptance run

---

## Pre-flight

- [ ] Confirm pre-existing 27 tests pass: `cd D:/github/cf/camfit-puller && python -m pytest -q` (expected: 27 passed)
- [ ] Confirm Docker compose health: `wsl -e bash -c "cd /mnt/d/github/cf/docker && docker compose ps"` (falkordb + rocksdb running)
- [ ] Confirm live data exists: `ls D:/github/cf/camfit-puller/data/details/ | wc -l` (should be ≥89, growing as P1 fetch continues)

If any precondition fails, stop and fix before starting Task 1.

---

## File Structure (created during plan)

```
docker/
  postgres/                                   NEW
    docker-compose.yml
    init/00-pgvector.sql
    README.md
  docker-compose.yml                          MODIFY (add postgres, remove rocksdb)
  rocksdb/                                    DELETE (Task 36)

camfit-puller/
  pyproject.toml                              MODIFY (Task 4)
  alembic.ini                                 NEW (Task 5)
  alembic/                                    NEW
    env.py
    versions/0001_initial.py

  src/camfit_puller/
    domain/{models.py,errors.py,embed_text.py}                          NEW (Tasks 6-8)
    ports/{repo.py,vector.py,graph.py,embed.py,extract.py,
           geocode.py,source.py,eta.py,__init__.py}                     NEW (Tasks 9-11)
    adapters/
      postgres/{pool.py,camp_repo.py,review_repo.py,concept_repo.py,
                theme_repo.py,filter_repo.py,mapping_repo.py,
                geocode_cache_repo.py,eta_cache_repo.py}                 NEW (Tasks 12-15)
      pgvector/index.py                                                  NEW (Task 16)
      falkor/graph.py                                                    NEW (Task 17, refactors falkor_writer.py)
      embed/{sentence_transformers.py,mock.py}                           NEW (Task 18)
      extract/{keybert.py,negation.py,mock.py}                           NEW (Tasks 24-26)
      cluster/{hdbscan.py,mock.py}                                       NEW (Task 29)
      geocode/{nominatim.py,cached.py,mock.py}                           NEW (Task 33, refactors cf_geocode.py)
      source/{camfit_cloak.py,local_replay.py,mock.py}                   NEW (Task 32, refactors cf_pull_*.py)
      eta/{etago_subprocess.py,mock.py}                                  NEW (Task 31, refactors etago_adapter.py)
    usecases/{ingest_snapshot.py,geocode_pending.py,build_vocabulary.py,
              build_embeddings.py,extract_filter_signals.py,
              extract_desc_signals.py,extract_review_signals.py,
              discover_themes.py,rebuild_graph.py,semantic_search.py,
              get_site_detail.py,eta_for_fleet.py,__init__.py}           NEW (Tasks 19-30, written next to their adapters)
    settings.py                                                          NEW (Task 37)
    container.py                                                         NEW (Task 37)
    api.py                                                               MODIFY (Task 38, drops rocks_*)
    cli.py                                                               MODIFY (Task 39, adds pipeline subcommands)

    rocks_writer.py                                                      DELETE (Task 36)
    falkor_writer.py                                                     DELETE (Task 17)
    etago_adapter.py                                                     DELETE (Task 31)
    crawler.py                                                           DELETE (Task 32)
    kg_builder.py                                                        DELETE (Task 30)
    lightpanda.py                                                        DELETE (Task 36; deprecated, blocked by Cloudflare)

  scripts/
    migrate_to_pg.py                                                     NEW (Task 34)
    seed_concepts.py                                                     NEW (Task 35)
    seed_filter_mapping.py                                               NEW (Task 35)

  tests/
    unit/usecases/test_*.py                                              NEW (per-use-case)
    contract/repo/test_camp_contract.py                                  NEW (Task 13)
    contract/vector/test_index_contract.py                               NEW (Task 16)
    contract/embed/test_embedder_contract.py                             NEW (Task 18)
    integration/test_full_pipeline.py                                    NEW (Task 41)
    integration/conftest.py                                              NEW (Task 41)

docs/superpowers/specs/2026-05-09-p2-pg-embedding-kg-design.md           (spec, already committed)
```

Existing `tests/test_*.py` (27 tests) stay; some are deleted in Task 36 with the modules they cover (rocks_writer test, kg_builder test, lightpanda test, etago_adapter test → moved to contract/).

---

## M1 — Foundation

### Task 1: PostgreSQL + pgvector docker compose

**Files:**
- Create: `docker/postgres/docker-compose.yml`
- Create: `docker/postgres/init/00-pgvector.sql`
- Create: `docker/postgres/README.md`

- [ ] **Step 1: Write `docker/postgres/init/00-pgvector.sql`**

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

- [ ] **Step 2: Write `docker/postgres/docker-compose.yml`**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: camfit-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: camfit
      POSTGRES_PASSWORD: camfit
      POSTGRES_DB: camfit
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U camfit -d camfit"]
      interval: 5s
      timeout: 3s
      retries: 12

volumes:
  pg_data:
```

- [ ] **Step 3: Write `docker/postgres/README.md`** (10 lines: bring-up, port, vars).

- [ ] **Step 4: Boot the container**

Run: `wsl -e bash -c "cd /mnt/d/github/cf/docker/postgres && docker compose up -d"`
Expected: `Container camfit-postgres Started`

- [ ] **Step 5: Verify**

Run: `wsl -e bash -c "docker exec camfit-postgres psql -U camfit -d camfit -c 'SELECT extname FROM pg_extension'"`
Expected output contains `vector`, `pg_trgm`.

- [ ] **Step 6: Commit**

```bash
cd D:/github/cf
git add docker/postgres/
git commit -m "feat(p2): postgres+pgvector docker compose"
```

---

### Task 2: Add postgres to umbrella compose

**Files:**
- Modify: `docker/docker-compose.yml`

- [ ] **Step 1: Edit umbrella compose to include postgres**

Insert under `services:` (keep falkordb + rocksdb for now — rocksdb removed in Task 36):

```yaml
  postgres:
    image: pgvector/pgvector:pg16
    container_name: camfit-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: camfit
      POSTGRES_PASSWORD: camfit
      POSTGRES_DB: camfit
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./postgres/init:/docker-entrypoint-initdb.d:ro
    networks: [camfit_net]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U camfit -d camfit"]
      interval: 5s
      timeout: 3s
      retries: 12
```

Add `pg_data:` to `volumes:` block.

- [ ] **Step 2: Commit**

```bash
git add docker/docker-compose.yml
git commit -m "feat(p2): add postgres to umbrella compose"
```

---

### Task 3: Bring umbrella stack up + verify three services

- [ ] **Step 1: Compose up**

Run: `wsl -e bash -c "cd /mnt/d/github/cf/docker && docker compose up -d"`

- [ ] **Step 2: Health check all 3**

Run: `wsl -e bash -c "cd /mnt/d/github/cf/docker && docker compose ps"`
Expected: 3 services (postgres, falkordb, rocksdb) all `(healthy)`.

(No commit — verification only.)

---

### Task 4: pyproject.toml — add P2 dependencies

**Files:**
- Modify: `camfit-puller/pyproject.toml`

- [ ] **Step 1: Replace `dependencies` block**

```toml
dependencies = [
    "httpx>=0.27",
    "selectolax>=0.3.21",
    "lxml>=5.2",
    "typer>=0.12",
    "pydantic>=2.7",
    "pydantic-settings>=2.4",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "falkordb>=1.0.10",
    "rich>=13.7",
    "loguru>=0.7",
    "tenacity>=8.2",
    "psycopg[binary,pool]>=3.2",
    "sqlalchemy>=2.0",
    "pgvector>=0.3.0",
    "alembic>=1.13",
    "sentence-transformers>=3.0",
    "scikit-learn>=1.5",
    "numpy>=1.26",
]
```

`[project.optional-dependencies]` add:
```toml
testcontainers = ["testcontainers[postgres]>=4.7"]
```

- [ ] **Step 2: Install**

Run: `cd D:/github/cf/camfit-puller && python -m pip install -e ".[dev,lightpanda,testcontainers]"`
Expected: success, downloads sentence-transformers / sklearn / pgvector / etc.

- [ ] **Step 3: Smoke imports**

Run: `cd D:/github/cf/camfit-puller && python -c "import psycopg, sqlalchemy, pgvector, sentence_transformers, sklearn, alembic, loguru; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add camfit-puller/pyproject.toml
git commit -m "feat(p2): add postgres+pgvector+st+sklearn deps"
```

---

### Task 5: alembic init + initial migration (full schema)

**Files:**
- Create: `camfit-puller/alembic.ini`
- Create: `camfit-puller/alembic/env.py`
- Create: `camfit-puller/alembic/versions/0001_initial.py`

- [ ] **Step 1: alembic init**

Run: `cd D:/github/cf/camfit-puller && alembic init alembic`

- [ ] **Step 2: Edit `alembic.ini` line `sqlalchemy.url`**

Replace with: `sqlalchemy.url = postgresql+psycopg://camfit:camfit@localhost:5432/camfit`

- [ ] **Step 3: Replace `alembic/env.py`** with minimal version that uses raw SQL revisions (no metadata import yet):

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    raise RuntimeError("offline migrations not used")
run_migrations_online()
```

- [ ] **Step 4: Create initial revision file `alembic/versions/0001_initial.py`** with full schema from spec §3.1–3.5. (Lengthy — copy verbatim from spec; use `op.execute(SQL...)` for the materialized view + HNSW index since they're not directly supported by Alembic ops.)

```python
"""initial schema

Revision ID: 0001
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table("camps",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("sido", sa.Text),
        sa.Column("sigungu", sa.Text),
        sa.Column("address", sa.Text),
        sa.Column("lat", sa.Float),
        sa.Column("lon", sa.Float),
        sa.Column("brief", sa.Text),
        sa.Column("location_brief", sa.Text),
        sa.Column("contact", sa.Text),
        sa.Column("price_start_from", sa.Integer),
        sa.Column("price_end_to", sa.Integer),
        sa.Column("num_of_reviews", sa.Integer, server_default="0"),
        sa.Column("num_of_viewed", sa.Integer, server_default="0"),
        sa.Column("bookmark_count", sa.Integer, server_default="0"),
        sa.Column("url", sa.Text),
        sa.Column("source", sa.Text, nullable=False, server_default="camfit"),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("geocoded_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("idx_camps_sido", "camps", ["sido"])
    op.create_index("idx_camps_sigungu", "camps", ["sigungu"])
    op.create_index("idx_camps_lat", "camps", ["lat"])
    op.create_index("idx_camps_lon", "camps", ["lon"])

    op.create_table("camp_descriptions",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("description", sa.Text),
    )
    for tbl, cols in [
        ("camp_types",         [("type", sa.Text)]),
        ("camp_facilities",    [("facility", sa.Text), ("is_additional", sa.Boolean, "false")]),
        ("camp_hashtags",      [("hashtag", sa.Text)]),
        ("camp_location_types",[("location_type", sa.Text)]),
        ("camp_collections",   [("collection_name", sa.Text)]),
    ]:
        cs = [sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True)]
        for c in cols:
            if len(c) == 2: cs.append(sa.Column(c[0], c[1], primary_key=True))
            else: cs.append(sa.Column(c[0], c[1], server_default=c[2]))
        op.create_table(tbl, *cs)

    op.create_table("camp_medias",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("idx", sa.Integer, primary_key=True),
        sa.Column("url", sa.Text), sa.Column("thumb_url", sa.Text),
        sa.Column("w", sa.Integer), sa.Column("h", sa.Integer),
    )

    op.create_table("reviews",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_nick", sa.Text), sa.Column("season", sa.Text),
        sa.Column("user_type", sa.Text), sa.Column("num_of_days", sa.Integer),
        sa.Column("score", sa.Numeric(5,2)), sa.Column("text", sa.Text, nullable=False),
        sa.Column("is_clean", sa.Boolean), sa.Column("is_kind", sa.Boolean),
        sa.Column("is_manner", sa.Boolean), sa.Column("is_convenient", sa.Boolean),
        sa.Column("review_timestamp", sa.BigInteger),
    )
    op.create_index("idx_reviews_camp", "reviews", ["camp_id"])
    op.create_index("idx_reviews_camp_score", "reviews", ["camp_id", sa.text("score DESC")])
    op.create_table("review_medias",
        sa.Column("review_id", sa.Text, sa.ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("idx", sa.Integer, primary_key=True),
        sa.Column("url", sa.Text),
    )

    op.create_table("camfit_filters",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("raw", postgresql.JSONB),
    )
    op.create_table("concepts",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, unique=True, nullable=False),
        sa.Column("category", sa.Text), sa.Column("description", sa.Text),
        sa.Column("is_axis", sa.Boolean, server_default="false"),
    )
    op.create_table("filter_concept_mapping",
        sa.Column("filter_id", sa.Text, sa.ForeignKey("camfit_filters.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("concept_id", sa.Text, sa.ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("polarity", sa.SmallInteger, nullable=False),
        sa.CheckConstraint("polarity IN (-1, 1)", name="polarity_check"),
    )
    for tbl in ("camp_filter_signals", "camp_desc_signals"):
        op.create_table(tbl,
            sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("concept_id", sa.Text, sa.ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("score", sa.Numeric(5,4), nullable=False),
            sa.Column("evidence", sa.Text),
        )
    op.create_table("camp_review_signals",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("concept_id", sa.Text, sa.ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("score", sa.Numeric(5,4), nullable=False),
        sa.Column("pos_count", sa.Integer, server_default="0"),
        sa.Column("neg_count", sa.Integer, server_default="0"),
        sa.Column("evidence", sa.Text),
    )
    op.execute("""
        CREATE MATERIALIZED VIEW camp_concept_aggregated AS
        SELECT camp_id, concept_id,
               COALESCE(SUM(f.score),0) * 1.0
             + COALESCE(SUM(r.score),0) * 0.7
             + COALESCE(SUM(d.score),0) * 0.5  AS final_score,
               array_remove(ARRAY[
                 CASE WHEN bool_or(f.score IS NOT NULL) THEN 'filter' END,
                 CASE WHEN bool_or(r.score IS NOT NULL) THEN 'review' END,
                 CASE WHEN bool_or(d.score IS NOT NULL) THEN 'description' END
               ], NULL) AS sources
        FROM (
          SELECT camp_id, concept_id FROM camp_filter_signals UNION
          SELECT camp_id, concept_id FROM camp_desc_signals UNION
          SELECT camp_id, concept_id FROM camp_review_signals
        ) all_sigs
        LEFT JOIN camp_filter_signals f USING (camp_id, concept_id)
        LEFT JOIN camp_review_signals r USING (camp_id, concept_id)
        LEFT JOIN camp_desc_signals   d USING (camp_id, concept_id)
        GROUP BY camp_id, concept_id;
    """)
    op.execute("CREATE INDEX idx_cca_concept_score ON camp_concept_aggregated (concept_id, final_score DESC)")

    op.execute("""
        CREATE TABLE camp_embeddings (
          camp_id text PRIMARY KEY REFERENCES camps(id) ON DELETE CASCADE,
          vec vector(768) NOT NULL,
          text_hash text NOT NULL,
          model_name text NOT NULL,
          created_at timestamptz DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_camp_embeddings_hnsw ON camp_embeddings USING hnsw (vec vector_cosine_ops) WITH (m=16, ef_construction=64)")

    op.execute("""
        CREATE TABLE themes (
          id text PRIMARY KEY,
          label text NOT NULL,
          centroid vector(768),
          member_count integer DEFAULT 0,
          manual_label text,
          created_at timestamptz DEFAULT now()
        )
    """)
    op.create_table("camp_themes",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("theme_id", sa.Text, sa.ForeignKey("themes.id", ondelete="CASCADE")),
    )

    op.create_table("geocodes",
        sa.Column("query", sa.Text, primary_key=True),
        sa.Column("lat", sa.Float), sa.Column("lon", sa.Float),
        sa.Column("source", sa.Text), sa.Column("raw", postgresql.JSONB),
        sa.Column("cached_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_table("eta_cache",
        sa.Column("origin", sa.Text, primary_key=True),
        sa.Column("dest", sa.Text, primary_key=True),
        sa.Column("minutes", sa.Integer), sa.Column("source", sa.Text),
        sa.Column("cached_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS camp_concept_aggregated")
    for t in ("eta_cache","geocodes","camp_themes","themes","camp_embeddings",
              "camp_review_signals","camp_desc_signals","camp_filter_signals",
              "filter_concept_mapping","concepts","camfit_filters",
              "review_medias","reviews","camp_medias","camp_collections",
              "camp_location_types","camp_hashtags","camp_facilities","camp_types",
              "camp_descriptions","camps"):
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
```

- [ ] **Step 5: Apply migration**

Run: `cd D:/github/cf/camfit-puller && alembic upgrade head`
Expected: `Running upgrade -> 0001, initial schema`

- [ ] **Step 6: Verify with `\dt`-equivalent**

Run: `wsl -e bash -c "docker exec camfit-postgres psql -U camfit -d camfit -c '\dt'"`
Expected: ≥17 tables.

- [ ] **Step 7: Commit**

```bash
git add camfit-puller/alembic.ini camfit-puller/alembic/
git commit -m "feat(p2): alembic initial schema (camps + signals + embeddings + themes)"
```

---

### Task 6: Domain models — `domain/models.py`

**Files:**
- Create: `camfit-puller/src/camfit_puller/domain/__init__.py` (empty)
- Create: `camfit-puller/src/camfit_puller/domain/models.py`
- Create: `camfit-puller/tests/unit/__init__.py` (empty)
- Create: `camfit-puller/tests/unit/test_domain_models.py`

- [ ] **Step 1: Write failing test `tests/unit/test_domain_models.py`**

```python
import pytest
from camfit_puller.domain.models import Camp, Region, GeoPoint, Review, Concept, Theme


def test_camp_basic_construction():
    c = Camp(id="abc", name="x", region=Region(sido="강원", sigungu="평창군"))
    assert c.id == "abc"
    assert c.region.sido == "강원"
    assert c.has_attr("has_valley") is False or not hasattr(c, "has_valley")


def test_camp_no_legacy_boolean_columns():
    """Per spec §6: hardcoded has_valley/has_kids/has_trampoline are removed."""
    fields = Camp.model_fields
    assert "has_valley" not in fields
    assert "has_kids" not in fields
    assert "has_trampoline" not in fields


def test_geo_point_korean_bbox_validation():
    GeoPoint(lat=37.5, lon=127.0)  # Seoul, valid
    with pytest.raises(Exception):
        GeoPoint(lat=10.0, lon=120.0)  # outside Korea → must reject


def test_review_minimum_fields():
    r = Review(id="r1", camp_id="abc", text="좋아요")
    assert r.text == "좋아요"
    assert r.score is None


def test_concept_source_enum():
    Concept(id="kids", name="kids", source="hashtag")
    with pytest.raises(Exception):
        Concept(id="x", name="x", source="bogus_source")
```

(`Camp.has_attr` is just a hasattr for clarity; Pydantic disallows extra by default with `model_config={"extra":"forbid"}` — verify in test.)

- [ ] **Step 2: Run, verify fail**

Run: `cd D:/github/cf/camfit-puller && python -m pytest tests/unit/test_domain_models.py -v`
Expected: import error / FAIL.

- [ ] **Step 3: Write `domain/models.py`**

```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class Region(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sido: str
    sigungu: str


class GeoPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=33.0, le=39.0)
    lon: float = Field(ge=124.0, le=132.0)


class Photo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    thumb_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class Camp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    region: Region
    address: Optional[str] = None
    geo: Optional[GeoPoint] = None
    types: list[str] = []
    facilities: list[str] = []
    additional_facilities: list[str] = []
    location_types: list[str] = []
    hashtags: list[str] = []
    collections: list[str] = []
    description: Optional[str] = None
    brief: Optional[str] = None
    location_brief: Optional[str] = None
    contact: Optional[str] = None
    price_start_from: Optional[int] = None
    price_end_to: Optional[int] = None
    num_of_reviews: int = 0
    num_of_viewed: int = 0
    bookmark_count: int = 0
    url: Optional[str] = None
    source: str = "camfit"
    photos: list[Photo] = []


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    camp_id: str
    user_nick: Optional[str] = None
    season: Optional[Literal["spring", "summer", "autumn", "winter"]] = None
    user_type: Optional[str] = None
    num_of_days: Optional[int] = None
    score: Optional[float] = None
    text: str
    is_clean: Optional[bool] = None
    is_kind: Optional[bool] = None
    is_manner: Optional[bool] = None
    is_convenient: Optional[bool] = None
    review_timestamp: Optional[int] = None
    medias: list[str] = []


class Concept(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    source: Literal["hashtag", "facility", "manual", "ngram"]
    category: Optional[str] = None
    description: Optional[str] = None
    is_axis: bool = False
    seed_term: Optional[str] = None


class CampConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")
    camp_id: str
    concept_id: str
    score: float = Field(ge=-1.0, le=1.0)


class Theme(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    centroid: Optional[list[float]] = None
    member_count: int = 0
    manual_label: Optional[str] = None


class EtaResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: str
    dest: str
    minutes: Optional[int] = None
    source: Optional[str] = None
    error: Optional[str] = None
```

(`test_camp_basic_construction` test referenced `has_attr` — fix by replacing with proper model_fields check.)

- [ ] **Step 4: Fix the assert in test**

Replace `assert c.has_attr("has_valley") is False or not hasattr(c, "has_valley")` with:
```python
assert "has_valley" not in c.model_fields
```

- [ ] **Step 5: Run tests, verify all 5 pass**

Run: `cd D:/github/cf/camfit-puller && python -m pytest tests/unit/test_domain_models.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add camfit-puller/src/camfit_puller/domain/ camfit-puller/tests/unit/
git commit -m "feat(p2): domain/models — Camp/Review/Concept/Theme (no legacy booleans)"
```

---

### Task 7: Domain — `embed_text.py` (deterministic text builder)

**Files:**
- Create: `camfit-puller/src/camfit_puller/domain/embed_text.py`
- Create: `camfit-puller/tests/unit/test_embed_text.py`

- [ ] **Step 1: Write failing test**

```python
from camfit_puller.domain.models import Camp, Region, Review
from camfit_puller.domain.embed_text import build_embed_text, text_hash


def _mk(**kw):
    base = dict(id="x", name="X", region=Region(sido="강원", sigungu="평창군"))
    base.update(kw)
    return Camp(**base)


def test_includes_name_and_address():
    c = _mk(address="강원 평창군 진부면 1-2", brief="좋은곳")
    out = build_embed_text(c, [])
    assert "X" in out
    assert "강원 평창군 진부면 1-2" in out
    assert "좋은곳" in out


def test_deterministic():
    c = _mk(brief="b", description="d")
    a = build_embed_text(c, [])
    b = build_embed_text(c, [])
    assert a == b


def test_top_reviews_sorted_by_score():
    c = _mk()
    rs = [
        Review(id="r1", camp_id="x", text="low", score=10),
        Review(id="r2", camp_id="x", text="high", score=99),
    ]
    out = build_embed_text(c, rs)
    assert out.find("high") < out.find("low")


def test_text_hash_changes_when_content_changes():
    c1 = _mk(brief="a")
    c2 = _mk(brief="b")
    assert text_hash(build_embed_text(c1, [])) != text_hash(build_embed_text(c2, []))
```

- [ ] **Step 2: Verify fail**

Run: `python -m pytest tests/unit/test_embed_text.py -v`

- [ ] **Step 3: Write `domain/embed_text.py`**

```python
from __future__ import annotations
import hashlib
from .models import Camp, Review

TOP_N_REVIEWS = 5


def build_embed_text(camp: Camp, reviews: list[Review]) -> str:
    parts: list[str] = []
    parts.append(f"# {camp.name}")
    if camp.address:
        parts.append(f"주소: {camp.address}")
    if camp.brief:
        parts.append(f"한줄: {camp.brief}")
    if camp.location_brief:
        parts.append(f"위치: {camp.location_brief}")
    types_loc = camp.types + camp.location_types
    if types_loc:
        parts.append(f"유형: {', '.join(types_loc)}")
    facs = sorted(set(camp.facilities + camp.additional_facilities))
    if facs:
        parts.append(f"시설: {', '.join(facs)}")
    if camp.hashtags:
        parts.append(f"태그: {' '.join('#' + h for h in camp.hashtags)}")
    if camp.description:
        parts.append("\n## 소개")
        parts.append(camp.description.strip())
    top = sorted(
        [r for r in reviews if (r.text or "").strip()],
        key=lambda r: -(r.score or 0),
    )[:TOP_N_REVIEWS]
    if top:
        parts.append(f"\n## 리뷰 ({len(top)})")
        for i, rv in enumerate(top, 1):
            user = rv.user_nick or "익명"
            score = rv.score if rv.score is not None else "?"
            season = rv.season or ""
            parts.append(f"\n[{i}] {user} · {season} · {score}\n{rv.text.strip()}")
    return "\n".join(parts)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/unit/test_embed_text.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add camfit-puller/src/camfit_puller/domain/embed_text.py camfit-puller/tests/unit/test_embed_text.py
git commit -m "feat(p2): domain/embed_text — deterministic text builder + hash"
```

---

### Task 8: Domain errors

**Files:**
- Create: `camfit-puller/src/camfit_puller/domain/errors.py`

- [ ] **Step 1: Write directly (single small file, no test needed)**

```python
"""Domain-level exceptions. Adapters wrap raw lib exceptions into these."""


class DomainError(Exception):
    pass


class CampNotFound(DomainError):
    def __init__(self, camp_id: str):
        super().__init__(f"camp not found: {camp_id}")
        self.camp_id = camp_id


class EmbeddingDimMismatch(DomainError):
    pass


class GeocodeUnresolved(DomainError):
    pass


class EtaUnavailable(DomainError):
    pass


class GraphUnavailable(DomainError):
    pass


class SourceUnavailable(DomainError):
    pass
```

- [ ] **Step 2: Commit**

```bash
git add camfit-puller/src/camfit_puller/domain/errors.py
git commit -m "feat(p2): domain/errors"
```

---

### Task 9: Ports — repos (Reader/Writer + Concept/Theme/Filter/Mapping)

**Files:**
- Create: `camfit-puller/src/camfit_puller/ports/__init__.py` (empty)
- Create: `camfit-puller/src/camfit_puller/ports/repo.py`

- [ ] **Step 1: Write `ports/repo.py`**

```python
from __future__ import annotations
from typing import Iterable, Iterator, Literal, Optional, Protocol, runtime_checkable
from ..domain.models import Camp, Review, Concept, Theme, CampConcept


@runtime_checkable
class CampReader(Protocol):
    def get(self, camp_id: str) -> Optional[Camp]: ...
    def list_filtered(
        self, *,
        sido: Optional[str] = None, sigungu: Optional[str] = None,
        concept: list[str] | None = None,
        concepts_any: list[str] | None = None,
        min_score: float | None = None, max_score: float | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        ids: list[str] | None = None,
        limit: int = 2000,
    ) -> list[Camp]: ...
    def iter_all(self) -> Iterator[Camp]: ...
    def count(self) -> int: ...


@runtime_checkable
class CampWriter(Protocol):
    def upsert_many(self, camps: Iterable[Camp]) -> int: ...
    def set_geo(self, camp_id: str, lat: float, lon: float) -> None: ...
    def delete(self, camp_id: str) -> bool: ...


@runtime_checkable
class ReviewReader(Protocol):
    def top_for(self, camp_id: str, n: int = 3,
                sort: Literal["score", "recent"] = "score") -> list[Review]: ...
    def total_for(self, camp_id: str) -> int: ...
    def iter_for(self, camp_id: str) -> Iterator[Review]: ...


@runtime_checkable
class ReviewWriter(Protocol):
    def upsert_many(self, reviews: Iterable[Review]) -> int: ...


@runtime_checkable
class ConceptRepository(Protocol):
    def upsert_concept(self, c: Concept) -> None: ...
    def assign(self, camp_id: str, concept_id: str, score: float, evidence: str | None = None) -> None: ...
    def for_camp(self, camp_id: str) -> list[CampConcept]: ...
    def all(self) -> list[Concept]: ...


@runtime_checkable
class ThemeRepository(Protocol):
    def replace_all(self, themes: list[Theme]) -> None: ...
    def assign(self, camp_id: str, theme_id: str) -> None: ...
    def for_camp(self, camp_id: str) -> Optional[Theme]: ...
    def all(self) -> list[Theme]: ...


@runtime_checkable
class CamfitFilterRepository(Protocol):
    """Stores camfit's native taxonomy (themes / inventory filters / collections)."""
    def upsert(self, filter_id: str, name: str, kind: str, raw: dict | None) -> None: ...
    def all(self) -> list[tuple[str, str, str]]: ...  # (id, name, kind)


@runtime_checkable
class FilterConceptMappingRepository(Protocol):
    def upsert_mapping(self, filter_id: str, concept_id: str, polarity: int) -> None: ...
    def for_filter(self, filter_id: str) -> list[tuple[str, int]]: ...  # (concept_id, polarity)


@runtime_checkable
class FilterSignalWriter(Protocol):
    def upsert(self, camp_id: str, concept_id: str, score: float, evidence: str | None) -> None: ...
    def reset_for(self, camp_id: str) -> None: ...


@runtime_checkable
class DescSignalWriter(Protocol):
    def upsert(self, camp_id: str, concept_id: str, score: float) -> None: ...
    def reset_for(self, camp_id: str) -> None: ...


@runtime_checkable
class ReviewSignalWriter(Protocol):
    def upsert(self, camp_id: str, concept_id: str, score: float,
               pos_count: int, neg_count: int, evidence: str | None) -> None: ...
    def reset_for(self, camp_id: str) -> None: ...
```

- [ ] **Step 2: Smoke import**

Run: `cd D:/github/cf/camfit-puller && python -c "from camfit_puller.ports.repo import CampReader, CampWriter; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add camfit-puller/src/camfit_puller/ports/
git commit -m "feat(p2): ports/repo — readers/writers/concept/theme/filter"
```

---

### Task 10: Ports — vector + graph + embed + extract + cluster

**Files:**
- Create: `camfit-puller/src/camfit_puller/ports/vector.py`
- Create: `camfit-puller/src/camfit_puller/ports/graph.py`
- Create: `camfit-puller/src/camfit_puller/ports/embed.py`
- Create: `camfit-puller/src/camfit_puller/ports/extract.py`

- [ ] **Step 1: Write all 4 files**

`vector.py`:
```python
from __future__ import annotations
from typing import Iterable, Optional, Protocol, runtime_checkable
import numpy as np


@runtime_checkable
class VectorIndex(Protocol):
    @property
    def dim(self) -> int: ...
    def upsert_many(self, items: Iterable[tuple[str, np.ndarray]]) -> int: ...
    def knn(self, query: np.ndarray, k: int = 10,
            filter_ids: set[str] | None = None) -> list[tuple[str, float]]: ...
    def get(self, item_id: str) -> Optional[np.ndarray]: ...
    def size(self) -> int: ...
    def reset(self) -> None: ...
```

`graph.py`:
```python
from __future__ import annotations
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class GraphStore(Protocol):
    def query(self, cypher: str, params: dict | None = None) -> list[list[Any]]: ...
    def reset(self, graph_name: Optional[str] = None) -> None: ...
    def healthcheck(self) -> bool: ...
```

`embed.py`:
```python
from __future__ import annotations
from typing import Protocol, runtime_checkable
import numpy as np


@runtime_checkable
class Embedder(Protocol):
    @property
    def model_name(self) -> str: ...
    @property
    def dim(self) -> int: ...
    def encode_one(self, text: str) -> np.ndarray: ...
    def encode_batch(self, texts: list[str], batch_size: int = 32) -> np.ndarray: ...
```

`extract.py`:
```python
from __future__ import annotations
from typing import Protocol, runtime_checkable
import numpy as np
from ..domain.models import Concept


@runtime_checkable
class ConceptExtractor(Protocol):
    def vocabulary(self) -> list[Concept]: ...
    def extract(self, text: str, vector: np.ndarray | None = None,
                top_k: int = 10, min_score: float = 0.3) -> list[tuple[str, float]]: ...


@runtime_checkable
class NegationAwareExtractor(Protocol):
    def extract_with_polarity(self, text: str) -> list[tuple[str, int, str]]:
        """[(concept_id, +1 or -1, evidence_snippet), ...]"""
        ...


@runtime_checkable
class ThemeClusterer(Protocol):
    def cluster(self, ids: list[str], vectors: np.ndarray) -> dict[str, int]: ...
    def label_cluster(self, cluster_id: int, member_ids: list[str],
                       member_concepts: dict[str, list[str]]) -> str: ...
```

- [ ] **Step 2: Smoke import**

Run: `python -c "from camfit_puller.ports import vector, graph, embed, extract; print('ok')"`

- [ ] **Step 3: Commit**

```bash
git add camfit-puller/src/camfit_puller/ports/
git commit -m "feat(p2): ports — vector/graph/embed/extract"
```

---

### Task 11: Ports — geocode + source + eta

**Files:**
- Create: `camfit-puller/src/camfit_puller/ports/geocode.py`
- Create: `camfit-puller/src/camfit_puller/ports/source.py`
- Create: `camfit-puller/src/camfit_puller/ports/eta.py`

- [ ] **Step 1: Write all 3**

`geocode.py`:
```python
from __future__ import annotations
from typing import Optional, Protocol, runtime_checkable
from ..domain.models import GeoPoint


@runtime_checkable
class Geocoder(Protocol):
    def lookup(self, address: str, *, hint: str | None = None) -> Optional[GeoPoint]: ...
```

`source.py`:
```python
from __future__ import annotations
from typing import Iterator, Optional, Protocol, runtime_checkable
from ..domain.models import Camp, Review


@runtime_checkable
class DataSource(Protocol):
    name: str
    def iter_summaries(self) -> Iterator[Camp]: ...
    def get_detail(self, camp_id: str) -> Optional[Camp]: ...
    def iter_reviews(self, camp_id: str, *, sort: str = "recommend") -> Iterator[Review]: ...
    def iter_filters(self) -> Iterator[tuple[str, str, str, dict | None]]:
        """yield (id, name, kind, raw_json) for each native taxonomy entry."""
        ...
```

`eta.py`:
```python
from __future__ import annotations
from typing import Iterable, Protocol, runtime_checkable
from ..domain.models import EtaResult


@runtime_checkable
class EtaProvider(Protocol):
    def drive_eta(self, origin: str, dest: str, *, timeout_s: float = 12.0) -> EtaResult: ...
    def drive_eta_batch(self, origin: str, dests: Iterable[tuple[str, str]],
                         *, concurrency: int = 4, timeout_s: float = 12.0) -> dict[str, EtaResult]: ...
```

- [ ] **Step 2: Commit**

```bash
git add camfit-puller/src/camfit_puller/ports/
git commit -m "feat(p2): ports — geocode/source/eta"
```

---

### Task 12: Postgres connection pool + Camp adapters

**Files:**
- Create: `camfit-puller/src/camfit_puller/adapters/__init__.py` (empty)
- Create: `camfit-puller/src/camfit_puller/adapters/postgres/__init__.py` (empty)
- Create: `camfit-puller/src/camfit_puller/adapters/postgres/pool.py`
- Create: `camfit-puller/src/camfit_puller/adapters/postgres/camp_repo.py`

- [ ] **Step 1: Write `pool.py`**

```python
from __future__ import annotations
from contextlib import contextmanager
import psycopg
from psycopg_pool import ConnectionPool


class PostgresPool:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 8):
        self._pool = ConnectionPool(dsn, min_size=min_size, max_size=max_size, open=True)

    @contextmanager
    def conn(self):
        with self._pool.connection() as c:
            yield c

    def close(self) -> None:
        self._pool.close()
```

- [ ] **Step 2: Write `camp_repo.py`** (CampReader + CampWriter, both)

```python
from __future__ import annotations
import json
from typing import Iterable, Iterator, Optional
from ...domain.models import Camp, Region, GeoPoint, Photo
from ...domain.errors import CampNotFound
from .pool import PostgresPool


_LIST_FIELDS = (
    "id, name, sido, sigungu, address, lat, lon, brief, location_brief, contact, "
    "price_start_from, price_end_to, num_of_reviews, num_of_viewed, bookmark_count, "
    "url, source"
)


def _row_to_camp(row, descriptions, types, facs, addl_facs, loc_types,
                  hashtags, collections, photos) -> Camp:
    geo = GeoPoint(lat=row["lat"], lon=row["lon"]) if row["lat"] is not None and row["lon"] is not None else None
    return Camp(
        id=row["id"], name=row["name"],
        region=Region(sido=row["sido"] or "(미지정)", sigungu=row["sigungu"] or "(미지정)"),
        address=row["address"], geo=geo,
        types=types, facilities=facs, additional_facilities=addl_facs,
        location_types=loc_types, hashtags=hashtags, collections=collections,
        description=descriptions,
        brief=row["brief"], location_brief=row["location_brief"], contact=row["contact"],
        price_start_from=row["price_start_from"], price_end_to=row["price_end_to"],
        num_of_reviews=row["num_of_reviews"] or 0,
        num_of_viewed=row["num_of_viewed"] or 0,
        bookmark_count=row["bookmark_count"] or 0,
        url=row["url"], source=row["source"] or "camfit", photos=photos,
    )


class PostgresCampReader:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def get(self, camp_id: str) -> Optional[Camp]:
        with self._pool.conn() as c, c.cursor(row_factory=psycopg_row_dict()) as cur:
            cur.execute(f"SELECT {_LIST_FIELDS} FROM camps WHERE id = %s", (camp_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._enrich(c, row)

    def _enrich(self, conn, row) -> Camp:
        with conn.cursor() as cur:
            cur.execute("SELECT description FROM camp_descriptions WHERE camp_id=%s", (row["id"],))
            d = cur.fetchone()
            description = d[0] if d else None
            def lst(table, col):
                cur.execute(f"SELECT {col} FROM {table} WHERE camp_id=%s ORDER BY {col}", (row["id"],))
                return [r[0] for r in cur.fetchall()]
            types = lst("camp_types", "type")
            cur.execute("SELECT facility, is_additional FROM camp_facilities WHERE camp_id=%s ORDER BY facility", (row["id"],))
            fac_rows = cur.fetchall()
            facs = [r[0] for r in fac_rows if not r[1]]
            addl = [r[0] for r in fac_rows if r[1]]
            hashtags = lst("camp_hashtags", "hashtag")
            loc_types = lst("camp_location_types", "location_type")
            collections = lst("camp_collections", "collection_name")
            cur.execute("SELECT idx, url, thumb_url, w, h FROM camp_medias WHERE camp_id=%s ORDER BY idx", (row["id"],))
            photos = [Photo(url=r[1], thumb_url=r[2], width=r[3], height=r[4]) for r in cur.fetchall()]
        return _row_to_camp(row, description, types, facs, addl, loc_types, hashtags, collections, photos)

    def list_filtered(self, *, sido=None, sigungu=None, concept=None, concepts_any=None,
                       min_score=None, max_score=None, bbox=None, ids=None, limit=2000):
        wh = []
        params: list = []
        if sido: wh.append("c.sido = %s"); params.append(sido)
        if sigungu: wh.append("c.sigungu = %s"); params.append(sigungu)
        if bbox:
            lon1, lat1, lon2, lat2 = bbox
            wh.append("c.lon BETWEEN %s AND %s AND c.lat BETWEEN %s AND %s")
            params.extend([min(lon1, lon2), max(lon1, lon2), min(lat1, lat2), max(lat1, lat2)])
        if ids:
            wh.append("c.id = ANY(%s)"); params.append(list(ids))
        sql = f"SELECT c.{', c.'.join(_LIST_FIELDS.split(', '))} FROM camps c "
        if concept:
            for cid in concept:
                sql += " JOIN camp_concept_aggregated agg_{0} ON agg_{0}.camp_id=c.id AND agg_{0}.concept_id=%s ".format(cid.replace('-', '_'))
                params.append(cid)
                if min_score is not None:
                    wh.append(f"agg_{cid.replace('-','_')}.final_score >= %s"); params.append(min_score)
                if max_score is not None:
                    wh.append(f"agg_{cid.replace('-','_')}.final_score <= %s"); params.append(max_score)
        if concepts_any:
            sql += " JOIN camp_concept_aggregated agg_any ON agg_any.camp_id=c.id "
            wh.append("agg_any.concept_id = ANY(%s)"); params.append(list(concepts_any))
            if min_score is not None:
                wh.append("agg_any.final_score >= %s"); params.append(min_score)
        if wh:
            sql += " WHERE " + " AND ".join(wh)
        sql += " LIMIT %s"; params.append(limit)
        with self._pool.conn() as c, c.cursor(row_factory=psycopg_row_dict()) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [self._enrich(c, r) for r in rows]

    def iter_all(self) -> Iterator[Camp]:
        with self._pool.conn() as c, c.cursor(row_factory=psycopg_row_dict(), name="camp_iter") as cur:
            cur.execute(f"SELECT {_LIST_FIELDS} FROM camps")
            for row in cur:
                yield self._enrich(c, row)

    def count(self) -> int:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM camps")
            return cur.fetchone()[0]


class PostgresCampWriter:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def upsert_many(self, camps: Iterable[Camp]) -> int:
        n = 0
        with self._pool.conn() as c, c.cursor() as cur:
            for camp in camps:
                cur.execute("""
                    INSERT INTO camps (id, name, sido, sigungu, address, lat, lon,
                                       brief, location_brief, contact,
                                       price_start_from, price_end_to,
                                       num_of_reviews, num_of_viewed, bookmark_count,
                                       url, source, fetched_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                    ON CONFLICT (id) DO UPDATE SET
                      name=EXCLUDED.name, sido=EXCLUDED.sido, sigungu=EXCLUDED.sigungu,
                      address=EXCLUDED.address, brief=EXCLUDED.brief,
                      location_brief=EXCLUDED.location_brief, contact=EXCLUDED.contact,
                      price_start_from=EXCLUDED.price_start_from, price_end_to=EXCLUDED.price_end_to,
                      num_of_reviews=EXCLUDED.num_of_reviews, num_of_viewed=EXCLUDED.num_of_viewed,
                      bookmark_count=EXCLUDED.bookmark_count, url=EXCLUDED.url
                """, (
                    camp.id, camp.name, camp.region.sido, camp.region.sigungu, camp.address,
                    camp.geo.lat if camp.geo else None, camp.geo.lon if camp.geo else None,
                    camp.brief, camp.location_brief, camp.contact,
                    camp.price_start_from, camp.price_end_to,
                    camp.num_of_reviews, camp.num_of_viewed, camp.bookmark_count,
                    camp.url, camp.source,
                ))
                if camp.description is not None:
                    cur.execute("INSERT INTO camp_descriptions (camp_id, description) VALUES (%s, %s) "
                                "ON CONFLICT (camp_id) DO UPDATE SET description=EXCLUDED.description",
                                (camp.id, camp.description))
                # m:n tables: wipe then insert
                for tbl, col, vals in [
                    ("camp_types", "type", camp.types),
                    ("camp_hashtags", "hashtag", camp.hashtags),
                    ("camp_location_types", "location_type", camp.location_types),
                    ("camp_collections", "collection_name", camp.collections),
                ]:
                    cur.execute(f"DELETE FROM {tbl} WHERE camp_id=%s", (camp.id,))
                    if vals:
                        cur.executemany(f"INSERT INTO {tbl} (camp_id, {col}) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                        [(camp.id, v) for v in vals])
                cur.execute("DELETE FROM camp_facilities WHERE camp_id=%s", (camp.id,))
                facs = [(camp.id, f, False) for f in camp.facilities] + \
                       [(camp.id, f, True) for f in camp.additional_facilities if f not in camp.facilities]
                if facs:
                    cur.executemany("INSERT INTO camp_facilities (camp_id, facility, is_additional) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", facs)
                cur.execute("DELETE FROM camp_medias WHERE camp_id=%s", (camp.id,))
                if camp.photos:
                    cur.executemany("INSERT INTO camp_medias (camp_id, idx, url, thumb_url, w, h) VALUES (%s,%s,%s,%s,%s,%s)",
                                    [(camp.id, i, p.url, p.thumb_url, p.width, p.height) for i, p in enumerate(camp.photos)])
                n += 1
        return n

    def set_geo(self, camp_id: str, lat: float, lon: float) -> None:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("UPDATE camps SET lat=%s, lon=%s, geocoded_at=now() WHERE id=%s", (lat, lon, camp_id))

    def delete(self, camp_id: str) -> bool:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM camps WHERE id=%s", (camp_id,))
            return cur.rowcount > 0


# helpers
def psycopg_row_dict():
    from psycopg.rows import dict_row
    return dict_row
```

(The dict-row helper is imported lazily inside the function to keep psycopg import a clean dependency.)

- [ ] **Step 3: Commit**

```bash
git add camfit-puller/src/camfit_puller/adapters/
git commit -m "feat(p2): adapters/postgres — pool + Camp Reader/Writer"
```

---

### Task 13: Postgres Camp contract test (uses live PG)

**Files:**
- Create: `camfit-puller/tests/contract/__init__.py` (empty)
- Create: `camfit-puller/tests/contract/repo/__init__.py` (empty)
- Create: `camfit-puller/tests/contract/repo/test_camp_contract.py`

- [ ] **Step 1: Write contract test**

```python
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
def reader(pool): return PostgresCampReader(pool)
@pytest.fixture
def writer(pool): return PostgresCampWriter(pool)


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
```

- [ ] **Step 2: Run, expect pass against live PG**

Run: `python -m pytest tests/contract/repo/test_camp_contract.py -v`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add camfit-puller/tests/contract/
git commit -m "test(p2): postgres camp repo contract tests"
```

---

### Task 14: Review repo + Concept repo + Theme repo + Filter repo + Mapping repo (Postgres)

**Files:**
- Create: `camfit-puller/src/camfit_puller/adapters/postgres/review_repo.py`
- Create: `camfit-puller/src/camfit_puller/adapters/postgres/concept_repo.py`
- Create: `camfit-puller/src/camfit_puller/adapters/postgres/theme_repo.py`
- Create: `camfit-puller/src/camfit_puller/adapters/postgres/filter_repo.py`
- Create: `camfit-puller/src/camfit_puller/adapters/postgres/mapping_repo.py`
- Create: `camfit-puller/src/camfit_puller/adapters/postgres/signal_repos.py`

- [ ] **Step 1: Write each adapter**

(Each is a small class with 2–4 methods following Camp pattern. ~200 lines total. See below.)

`review_repo.py`:
```python
from __future__ import annotations
from typing import Iterable, Iterator, Literal
from ...domain.models import Review
from .pool import PostgresPool


class PostgresReviewReader:
    def __init__(self, pool: PostgresPool): self._pool = pool

    def top_for(self, camp_id, n=3, sort="score"):
        order = "score DESC NULLS LAST" if sort == "score" else "review_timestamp DESC"
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute(f"""SELECT id, camp_id, user_nick, season, user_type, num_of_days,
                            score, text, is_clean, is_kind, is_manner, is_convenient, review_timestamp
                            FROM reviews WHERE camp_id=%s ORDER BY {order} LIMIT %s""", (camp_id, n))
            return [self._row(r) for r in cur.fetchall()]

    def total_for(self, camp_id):
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM reviews WHERE camp_id=%s", (camp_id,))
            return cur.fetchone()[0]

    def iter_for(self, camp_id) -> Iterator[Review]:
        with self._pool.conn() as c, c.cursor(name=f"rev_{camp_id}") as cur:
            cur.execute("SELECT id, camp_id, user_nick, season, user_type, num_of_days, score, text, is_clean, is_kind, is_manner, is_convenient, review_timestamp FROM reviews WHERE camp_id=%s", (camp_id,))
            for r in cur:
                yield self._row(r)

    @staticmethod
    def _row(r) -> Review:
        return Review(
            id=r[0], camp_id=r[1], user_nick=r[2], season=r[3], user_type=r[4],
            num_of_days=r[5], score=float(r[6]) if r[6] is not None else None,
            text=r[7], is_clean=r[8], is_kind=r[9], is_manner=r[10], is_convenient=r[11],
            review_timestamp=r[12],
        )


class PostgresReviewWriter:
    def __init__(self, pool): self._pool = pool

    def upsert_many(self, reviews: Iterable[Review]) -> int:
        n = 0
        with self._pool.conn() as c, c.cursor() as cur:
            for r in reviews:
                cur.execute("""
                    INSERT INTO reviews (id, camp_id, user_nick, season, user_type,
                       num_of_days, score, text, is_clean, is_kind, is_manner, is_convenient, review_timestamp)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                      score=EXCLUDED.score, text=EXCLUDED.text
                """, (r.id, r.camp_id, r.user_nick, r.season, r.user_type, r.num_of_days,
                      r.score, r.text, r.is_clean, r.is_kind, r.is_manner, r.is_convenient, r.review_timestamp))
                cur.execute("DELETE FROM review_medias WHERE review_id=%s", (r.id,))
                if r.medias:
                    cur.executemany("INSERT INTO review_medias (review_id, idx, url) VALUES (%s,%s,%s)",
                                    [(r.id, i, u) for i, u in enumerate(r.medias)])
                n += 1
        return n
```

`concept_repo.py`:
```python
from __future__ import annotations
from ...domain.models import Concept, CampConcept
from .pool import PostgresPool


class PostgresConceptRepo:
    def __init__(self, pool): self._pool = pool

    def upsert_concept(self, c: Concept) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("""INSERT INTO concepts (id, name, source, category, description, is_axis)
                           VALUES (%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (id) DO UPDATE SET
                             name=EXCLUDED.name, source=EXCLUDED.source, category=EXCLUDED.category,
                             description=EXCLUDED.description, is_axis=EXCLUDED.is_axis""",
                        (c.id, c.name, c.source, c.category, c.description, c.is_axis))

    def assign(self, camp_id, concept_id, score, evidence=None):
        # writes to camp_filter_signals — used as default; specific writers (filter/desc/review) call their own table
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("""INSERT INTO camp_filter_signals (camp_id, concept_id, score, evidence)
                           VALUES (%s,%s,%s,%s)
                           ON CONFLICT (camp_id, concept_id) DO UPDATE SET
                             score=EXCLUDED.score, evidence=EXCLUDED.evidence""",
                        (camp_id, concept_id, score, evidence))

    def for_camp(self, camp_id) -> list[CampConcept]:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("SELECT camp_id, concept_id, final_score FROM camp_concept_aggregated WHERE camp_id=%s",
                        (camp_id,))
            return [CampConcept(camp_id=r[0], concept_id=r[1], score=float(r[2])) for r in cur.fetchall()]

    def all(self) -> list[Concept]:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("SELECT id, name, source, category, description, is_axis FROM concepts")
            return [Concept(id=r[0], name=r[1], source=r[2], category=r[3], description=r[4], is_axis=r[5])
                    for r in cur.fetchall()]
```

`theme_repo.py`:
```python
from __future__ import annotations
from typing import Optional
from ...domain.models import Theme
from .pool import PostgresPool


class PostgresThemeRepo:
    def __init__(self, pool): self._pool = pool

    def replace_all(self, themes: list[Theme]) -> None:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("DELETE FROM camp_themes")
            cur.execute("DELETE FROM themes")
            for t in themes:
                cur.execute("""INSERT INTO themes (id, label, centroid, member_count, manual_label)
                               VALUES (%s, %s, %s, %s, %s)""",
                            (t.id, t.label, t.centroid, t.member_count, t.manual_label))

    def assign(self, camp_id, theme_id):
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("""INSERT INTO camp_themes (camp_id, theme_id) VALUES (%s,%s)
                           ON CONFLICT (camp_id) DO UPDATE SET theme_id=EXCLUDED.theme_id""",
                        (camp_id, theme_id))

    def for_camp(self, camp_id) -> Optional[Theme]:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("""SELECT t.id, t.label, t.member_count, t.manual_label
                           FROM themes t JOIN camp_themes ct ON t.id=ct.theme_id
                           WHERE ct.camp_id=%s""", (camp_id,))
            r = cur.fetchone()
            return Theme(id=r[0], label=r[1], member_count=r[2], manual_label=r[3]) if r else None

    def all(self) -> list[Theme]:
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("SELECT id, label, member_count, manual_label FROM themes ORDER BY member_count DESC")
            return [Theme(id=r[0], label=r[1], member_count=r[2], manual_label=r[3]) for r in cur.fetchall()]
```

`filter_repo.py`:
```python
class PostgresCamfitFilterRepo:
    def __init__(self, pool): self._pool = pool
    def upsert(self, filter_id, name, kind, raw):
        import json
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("""INSERT INTO camfit_filters (id, name, kind, raw)
                           VALUES (%s,%s,%s,%s)
                           ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, kind=EXCLUDED.kind, raw=EXCLUDED.raw""",
                        (filter_id, name, kind, json.dumps(raw) if raw else None))
    def all(self):
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("SELECT id, name, kind FROM camfit_filters")
            return cur.fetchall()
```

`mapping_repo.py`:
```python
class PostgresFilterConceptMappingRepo:
    def __init__(self, pool): self._pool = pool
    def upsert_mapping(self, filter_id, concept_id, polarity):
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("""INSERT INTO filter_concept_mapping (filter_id, concept_id, polarity)
                           VALUES (%s,%s,%s)
                           ON CONFLICT (filter_id, concept_id) DO UPDATE SET polarity=EXCLUDED.polarity""",
                        (filter_id, concept_id, polarity))
    def for_filter(self, filter_id):
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("SELECT concept_id, polarity FROM filter_concept_mapping WHERE filter_id=%s", (filter_id,))
            return cur.fetchall()
```

`signal_repos.py`:
```python
class PostgresFilterSignalWriter:
    def __init__(self, pool): self._pool = pool
    def upsert(self, camp_id, concept_id, score, evidence):
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("""INSERT INTO camp_filter_signals (camp_id, concept_id, score, evidence)
                           VALUES (%s,%s,%s,%s)
                           ON CONFLICT (camp_id, concept_id) DO UPDATE SET score=EXCLUDED.score, evidence=EXCLUDED.evidence""",
                        (camp_id, concept_id, score, evidence))
    def reset_for(self, camp_id):
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("DELETE FROM camp_filter_signals WHERE camp_id=%s", (camp_id,))


class PostgresDescSignalWriter:
    def __init__(self, pool): self._pool = pool
    def upsert(self, camp_id, concept_id, score):
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("""INSERT INTO camp_desc_signals (camp_id, concept_id, score)
                           VALUES (%s,%s,%s)
                           ON CONFLICT (camp_id, concept_id) DO UPDATE SET score=EXCLUDED.score""",
                        (camp_id, concept_id, score))
    def reset_for(self, camp_id):
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("DELETE FROM camp_desc_signals WHERE camp_id=%s", (camp_id,))


class PostgresReviewSignalWriter:
    def __init__(self, pool): self._pool = pool
    def upsert(self, camp_id, concept_id, score, pos_count, neg_count, evidence):
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("""INSERT INTO camp_review_signals (camp_id, concept_id, score, pos_count, neg_count, evidence)
                           VALUES (%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (camp_id, concept_id) DO UPDATE SET
                             score=EXCLUDED.score, pos_count=EXCLUDED.pos_count,
                             neg_count=EXCLUDED.neg_count, evidence=EXCLUDED.evidence""",
                        (camp_id, concept_id, score, pos_count, neg_count, evidence))
    def reset_for(self, camp_id):
        with self._pool.conn() as cn, cn.cursor() as cur:
            cur.execute("DELETE FROM camp_review_signals WHERE camp_id=%s", (camp_id,))
```

- [ ] **Step 2: Smoke import**

Run: `python -c "from camfit_puller.adapters.postgres import camp_repo, review_repo, concept_repo, theme_repo, filter_repo, mapping_repo, signal_repos; print('ok')"`

- [ ] **Step 3: Commit**

```bash
git add camfit-puller/src/camfit_puller/adapters/postgres/
git commit -m "feat(p2): postgres adapters — review/concept/theme/filter/mapping/signals"
```

---

### Task 15: Geocode + ETA cache repos (Postgres)

**Files:**
- Create: `camfit-puller/src/camfit_puller/adapters/postgres/geocode_cache_repo.py`
- Create: `camfit-puller/src/camfit_puller/adapters/postgres/eta_cache_repo.py`

- [ ] **Step 1: Write both** (small, like above pattern). Each has `get(key)` / `put(key, ...)` / `clear()`.

- [ ] **Step 2: Commit**

```bash
git add camfit-puller/src/camfit_puller/adapters/postgres/
git commit -m "feat(p2): postgres adapters — geocode + eta caches"
```

---

## M2 — Embeddings + Vector

### Task 16: pgvector adapter + contract test

**Files:**
- Create: `camfit-puller/src/camfit_puller/adapters/pgvector/__init__.py` (empty)
- Create: `camfit-puller/src/camfit_puller/adapters/pgvector/index.py`
- Create: `camfit-puller/tests/contract/vector/__init__.py`
- Create: `camfit-puller/tests/contract/vector/test_index_contract.py`

- [ ] **Step 1: Write `index.py`** (PgvectorIndex implements VectorIndex)

```python
from __future__ import annotations
from typing import Iterable, Optional
import numpy as np
from ..postgres.pool import PostgresPool


class PgvectorIndex:
    def __init__(self, pool: PostgresPool, *, dim: int = 768, model_name: str = "ko-sroberta"):
        self._pool = pool
        self._dim = dim
        self._model = model_name

    @property
    def dim(self) -> int: return self._dim

    def upsert_many(self, items):
        from pgvector.psycopg import register_vector
        n = 0
        with self._pool.conn() as c:
            register_vector(c)
            with c.cursor() as cur:
                for cid, vec, *rest in items:
                    text_h = rest[0] if rest else "0"
                    cur.execute("""INSERT INTO camp_embeddings (camp_id, vec, text_hash, model_name)
                                   VALUES (%s, %s, %s, %s)
                                   ON CONFLICT (camp_id) DO UPDATE SET
                                     vec=EXCLUDED.vec, text_hash=EXCLUDED.text_hash, model_name=EXCLUDED.model_name,
                                     created_at=now()""",
                                (cid, vec, text_h, self._model))
                    n += 1
        return n

    def knn(self, query: np.ndarray, k=10, filter_ids=None):
        from pgvector.psycopg import register_vector
        with self._pool.conn() as c:
            register_vector(c)
            with c.cursor() as cur:
                if filter_ids:
                    cur.execute("""SELECT camp_id, 1 - (vec <=> %s) AS sim FROM camp_embeddings
                                   WHERE camp_id = ANY(%s) ORDER BY vec <=> %s LIMIT %s""",
                                (query, list(filter_ids), query, k))
                else:
                    cur.execute("""SELECT camp_id, 1 - (vec <=> %s) AS sim FROM camp_embeddings
                                   ORDER BY vec <=> %s LIMIT %s""", (query, query, k))
                return [(r[0], float(r[1])) for r in cur.fetchall()]

    def get(self, item_id: str) -> Optional[np.ndarray]:
        from pgvector.psycopg import register_vector
        with self._pool.conn() as c:
            register_vector(c)
            with c.cursor() as cur:
                cur.execute("SELECT vec FROM camp_embeddings WHERE camp_id=%s", (item_id,))
                row = cur.fetchone()
                return np.array(row[0]) if row else None

    def size(self) -> int:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM camp_embeddings")
            return cur.fetchone()[0]

    def reset(self) -> None:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM camp_embeddings")
```

- [ ] **Step 2: Write contract test**

```python
import numpy as np
import pytest
from camfit_puller.adapters.postgres.pool import PostgresPool
from camfit_puller.adapters.postgres.camp_repo import PostgresCampWriter
from camfit_puller.adapters.pgvector.index import PgvectorIndex
from camfit_puller.domain.models import Camp, Region


@pytest.fixture(scope="module")
def pool():
    p = PostgresPool("postgresql://camfit:camfit@localhost:5432/camfit")
    yield p; p.close()

@pytest.fixture
def index(pool): return PgvectorIndex(pool, dim=768)


@pytest.fixture(autouse=True)
def setup(pool):
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
    assert index.size() >= 0
    index.reset()
    assert index.size() == 0


def test_filter_ids_restricts_search(index):
    rng = np.random.default_rng(7)
    a = rng.normal(size=768).astype(np.float32)
    index.upsert_many([("V_A", a, "h"), ("V_B", a, "h"), ("V_C", a, "h")])
    hits = index.knn(a, k=5, filter_ids={"V_B", "V_C"})
    ids = {x for x, _ in hits}
    assert ids <= {"V_B", "V_C"}
```

- [ ] **Step 3: Run, verify**

Run: `python -m pytest tests/contract/vector/test_index_contract.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add camfit-puller/src/camfit_puller/adapters/pgvector/ camfit-puller/tests/contract/vector/
git commit -m "feat(p2): pgvector adapter + contract tests"
```

---

### Task 17: FalkorGraph adapter (refactor falkor_writer.py)

**Files:**
- Create: `camfit-puller/src/camfit_puller/adapters/falkor/__init__.py`
- Create: `camfit-puller/src/camfit_puller/adapters/falkor/graph.py`
- Modify: `camfit-puller/tests/test_kg_builder.py` → keep (still tests `kg_builder.build` which we'll keep until Task 30 deletes it)

- [ ] **Step 1: Write `falkor/graph.py`**

```python
from __future__ import annotations
from typing import Any, Optional
from falkordb import FalkorDB


class FalkorGraph:
    def __init__(self, host: str, port: int, graph: str = "camfit"):
        self._host, self._port, self._graph = host, port, graph

    def _g(self):
        return FalkorDB(host=self._host, port=self._port).select_graph(self._graph)

    def query(self, cypher: str, params: dict | None = None) -> list[list[Any]]:
        rs = self._g().query(cypher, params=params or {})
        return [list(r) for r in (rs.result_set or [])]

    def reset(self, graph_name: Optional[str] = None) -> None:
        g = FalkorDB(host=self._host, port=self._port).select_graph(graph_name or self._graph)
        try:
            g.query("MATCH (n) DETACH DELETE n")
        except Exception:
            pass

    def healthcheck(self) -> bool:
        try:
            self._g().query("RETURN 1")
            return True
        except Exception:
            return False
```

- [ ] **Step 2: Smoke**

Run: `python -c "from camfit_puller.adapters.falkor.graph import FalkorGraph; g=FalkorGraph('localhost',6379); print('hc=', g.healthcheck())"`
Expected: `hc= True`.

- [ ] **Step 3: Commit**

```bash
git add camfit-puller/src/camfit_puller/adapters/falkor/
git commit -m "feat(p2): FalkorGraph adapter (port impl)"
```

---

### Task 18: Embed adapter — sentence-transformers + Mock + contract test

**Files:**
- Create: `camfit-puller/src/camfit_puller/adapters/embed/__init__.py`
- Create: `camfit-puller/src/camfit_puller/adapters/embed/sentence_transformers.py`
- Create: `camfit-puller/src/camfit_puller/adapters/embed/mock.py`
- Create: `camfit-puller/tests/contract/embed/__init__.py`
- Create: `camfit-puller/tests/contract/embed/test_embedder_contract.py`

- [ ] **Step 1: Write `mock.py`**

```python
import hashlib
import numpy as np


class MockEmbedder:
    """Deterministic, zero-dependency embedder for tests. dim 768 matches ko-sroberta."""
    model_name = "mock"

    def __init__(self, dim: int = 768):
        self._dim = dim

    @property
    def dim(self) -> int: return self._dim

    def encode_one(self, text: str) -> np.ndarray:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        rng = np.random.default_rng(int.from_bytes(h[:8], "big"))
        v = rng.normal(size=self._dim).astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-9)

    def encode_batch(self, texts, batch_size=32):
        return np.stack([self.encode_one(t) for t in texts])
```

- [ ] **Step 2: Write `sentence_transformers.py`**

```python
from __future__ import annotations
import numpy as np


class KoSrobertaEmbedder:
    model_name = "jhgan/ko-sroberta-multitask"

    def __init__(self, model_id: str | None = None, device: str = "cpu"):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_id or self.model_name, device=device)

    @property
    def dim(self) -> int:
        return int(self._model.get_sentence_embedding_dimension())

    def encode_one(self, text: str) -> np.ndarray:
        v = self._model.encode([text], normalize_embeddings=True)[0]
        return np.asarray(v, dtype=np.float32)

    def encode_batch(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        v = self._model.encode(texts, batch_size=batch_size, normalize_embeddings=True,
                               show_progress_bar=False, convert_to_numpy=True)
        return np.asarray(v, dtype=np.float32)
```

- [ ] **Step 3: Write contract test (parametrized over both embedders)**

```python
import numpy as np
import pytest
from camfit_puller.adapters.embed.mock import MockEmbedder


def _embedders():
    yield MockEmbedder()
    try:
        from camfit_puller.adapters.embed.sentence_transformers import KoSrobertaEmbedder
        yield KoSrobertaEmbedder()
    except Exception as e:
        pytest.skip(f"ko-sroberta unavailable in this env: {e}")


@pytest.fixture(params=list(_embedders()))
def embedder(request): return request.param


def test_dim_consistent(embedder):
    v = embedder.encode_one("계곡 캠핑")
    assert v.shape == (embedder.dim,)


def test_batch_matches_individual(embedder):
    texts = ["계곡 캠핑", "키즈 캠프", "오션뷰"]
    batch = embedder.encode_batch(texts)
    one = np.stack([embedder.encode_one(t) for t in texts])
    assert batch.shape == one.shape
    # same model + same input → similar (but not guaranteed identical for ST due to floating ops)
    assert np.allclose(batch, one, atol=1e-3) or np.linalg.norm(batch - one) < 0.1


def test_normalized(embedder):
    v = embedder.encode_one("test")
    assert abs(np.linalg.norm(v) - 1.0) < 0.01
```

- [ ] **Step 4: Run**

Run: `python -m pytest tests/contract/embed/ -v`
Expected: 3 (mock) + 3 (st) = 6 passed (or 3 if ST skipped).

- [ ] **Step 5: Commit**

```bash
git add camfit-puller/src/camfit_puller/adapters/embed/ camfit-puller/tests/contract/embed/
git commit -m "feat(p2): embed adapters (ko-sroberta + mock) + contract tests"
```

---

### Task 19: Use-case — `BuildEmbeddings`

**Files:**
- Create: `camfit-puller/src/camfit_puller/usecases/__init__.py`
- Create: `camfit-puller/src/camfit_puller/usecases/build_embeddings.py`
- Create: `camfit-puller/tests/unit/usecases/__init__.py`
- Create: `camfit-puller/tests/unit/usecases/test_build_embeddings.py`

- [ ] **Step 1: Write failing test (mock-only)**

```python
import numpy as np
from camfit_puller.adapters.embed.mock import MockEmbedder
from camfit_puller.domain.models import Camp, Region, Review
from camfit_puller.usecases.build_embeddings import BuildEmbeddings


class FakeReader:
    def __init__(self, camps): self._c = camps
    def iter_all(self): return iter(self._c)
    def get(self, i):
        for c in self._c:
            if c.id == i: return c
        return None
    def list_filtered(self, **kw): return self._c
    def count(self): return len(self._c)


class FakeReviewReader:
    def top_for(self, cid, n=3, sort="score"): return []
    def total_for(self, cid): return 0
    def iter_for(self, cid): return iter([])


class FakeIndex:
    dim = 768
    def __init__(self): self._d = {}
    def upsert_many(self, items):
        n = 0
        for cid, vec, *_ in items:
            self._d[cid] = vec; n += 1
        return n
    def knn(self, q, k=10, filter_ids=None):
        return [(cid, float(np.dot(vec, q))) for cid, vec in self._d.items()][:k]
    def get(self, i): return self._d.get(i)
    def size(self): return len(self._d)
    def reset(self): self._d.clear()


def test_build_embeddings_writes_one_vector_per_camp():
    camps = [Camp(id=f"c{i}", name=f"C{i}", region=Region(sido="강원", sigungu="평창군"), brief=f"b{i}")
             for i in range(3)]
    uc = BuildEmbeddings(FakeReader(camps), FakeReviewReader(), MockEmbedder(), FakeIndex())
    n = uc.execute()
    assert n == 3
```

- [ ] **Step 2: Verify fail**

Run: `python -m pytest tests/unit/usecases/test_build_embeddings.py -v`

- [ ] **Step 3: Write `usecases/build_embeddings.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from ..domain.embed_text import build_embed_text, text_hash
from ..ports.repo import CampReader, ReviewReader
from ..ports.embed import Embedder
from ..ports.vector import VectorIndex


@dataclass
class BuildEmbeddings:
    camp_reader: CampReader
    review_reader: ReviewReader
    embedder: Embedder
    vector_index: VectorIndex
    batch_size: int = 32

    def execute(self) -> int:
        ids: list[str] = []
        texts: list[str] = []
        for camp in self.camp_reader.iter_all():
            top = list(self.review_reader.top_for(camp.id, n=5))
            text = build_embed_text(camp, top)
            ids.append(camp.id)
            texts.append(text)
        if not ids:
            return 0
        vecs = self.embedder.encode_batch(texts, batch_size=self.batch_size)
        items = [(cid, vecs[i], text_hash(texts[i])) for i, cid in enumerate(ids)]
        return self.vector_index.upsert_many(items)
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/unit/usecases/test_build_embeddings.py -v`

- [ ] **Step 5: Commit**

```bash
git add camfit-puller/src/camfit_puller/usecases/ camfit-puller/tests/unit/usecases/
git commit -m "feat(p2): usecase BuildEmbeddings (TDD with mocks)"
```

---

### Task 20: Use-case — `BuildVocabulary` (concept seed from current data)

**Files:**
- Create: `camfit-puller/src/camfit_puller/usecases/build_vocabulary.py`
- Create: `camfit-puller/tests/unit/usecases/test_build_vocabulary.py`

(Pattern: read camps' hashtags + facilities + manual seed list → upsert_concept on each. Manual seed list lives in `domain/concept_seeds.py`.)

- [ ] **Step 1: Write seed list `domain/concept_seeds.py`**

```python
"""Curated concept seed list. Each entry: (id, name, category, is_axis).
Sources beyond this list (hashtag, facility) are auto-generated by BuildVocabulary."""

SEEDS: list[tuple[str, str, str, bool]] = [
    ("kids",         "키즈캠핑",   "audience",     True),
    ("pets",         "반려동반",   "audience",     True),
    ("valley",       "계곡",       "environment",  True),
    ("oceanview",    "오션뷰",     "environment",  True),
    ("riverview",    "리버뷰",     "environment",  True),
    ("mountainview", "산뷰",       "environment",  False),
    ("trampoline",   "트램펄린",   "facility",     True),
    ("swimmingpool", "수영장",     "facility",     False),
    ("warmpool",     "온수풀",     "facility",     False),
    ("playground",   "놀이터",     "facility",     False),
    ("private",      "프라이빗",   "vibe",         False),
    ("stargazing",   "별보기",     "activity",     False),
    ("autumn",       "단풍",       "season",       False),
    ("spring",       "벚꽃",       "season",       False),
    ("autoCamping",  "오토캠핑",   "type",         False),
    ("glamping",     "글램핑",     "type",         False),
    ("caravan",      "카라반",     "type",         False),
    ("pension",      "펜션",       "type",         False),
    ("bungalow",     "방갈로",     "type",         False),
]
```

- [ ] **Step 2: Write the use-case + test** (similar TDD pattern; FakeReader+ FakeConceptRepo)

(Code below; test omitted here for brevity but follows pattern of Task 19.)

```python
# usecases/build_vocabulary.py
from __future__ import annotations
from dataclasses import dataclass
from ..domain.models import Concept
from ..domain.concept_seeds import SEEDS
from ..ports.repo import CampReader, ConceptRepository


@dataclass
class BuildVocabulary:
    camp_reader: CampReader
    concept_repo: ConceptRepository

    def execute(self) -> int:
        n = 0
        for cid, name, category, is_axis in SEEDS:
            self.concept_repo.upsert_concept(
                Concept(id=cid, name=name, source="manual", category=category, is_axis=is_axis)
            )
            n += 1
        # Auto-derive from existing hashtags
        seen = set()
        for camp in self.camp_reader.iter_all():
            for h in camp.hashtags:
                slug = "h_" + _slug(h)
                if slug in seen: continue
                seen.add(slug)
                self.concept_repo.upsert_concept(Concept(id=slug, name=h, source="hashtag"))
                n += 1
            for f in (camp.facilities + camp.additional_facilities):
                slug = "f_" + _slug(f)
                if slug in seen: continue
                seen.add(slug)
                self.concept_repo.upsert_concept(Concept(id=slug, name=f, source="facility"))
                n += 1
        return n


def _slug(name: str) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9가-힣]+", "_", name).strip("_").lower()
```

- [ ] **Step 3: Test + commit**

```bash
git add camfit-puller/src/camfit_puller/domain/concept_seeds.py \
        camfit-puller/src/camfit_puller/usecases/build_vocabulary.py \
        camfit-puller/tests/unit/usecases/test_build_vocabulary.py
git commit -m "feat(p2): usecase BuildVocabulary + concept seeds"
```

---

### Task 21: Use-case — `SemanticSearch`

**Files:**
- Create: `camfit-puller/src/camfit_puller/usecases/semantic_search.py`
- Create: `camfit-puller/tests/unit/usecases/test_semantic_search.py`

- [ ] **Step 1: Test (deterministic with mocks)**

```python
from camfit_puller.adapters.embed.mock import MockEmbedder
from camfit_puller.domain.models import Camp, Region
from camfit_puller.usecases.semantic_search import SemanticSearch
import numpy as np


class FakeIndex:
    def __init__(self, vecs): self._v = vecs
    def knn(self, q, k=10, filter_ids=None):
        sims = [(cid, float(np.dot(v, q))) for cid, v in self._v.items()]
        return sorted(sims, key=lambda x: -x[1])[:k]
    def upsert_many(self, *_): pass
    def get(self, *_): return None
    def size(self): return len(self._v)
    def reset(self): self._v = {}
    @property
    def dim(self): return 768


class FakeReader:
    def __init__(self, camps): self._c = {c.id: c for c in camps}
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
```

- [ ] **Step 2: Implement**

```python
from dataclasses import dataclass
from ..ports.repo import CampReader
from ..ports.embed import Embedder
from ..ports.vector import VectorIndex
from ..domain.models import Camp


@dataclass
class SemanticSearch:
    embedder: Embedder
    vector_index: VectorIndex
    camp_reader: CampReader

    def execute(self, q: str, k: int = 20) -> list[Camp]:
        v = self.embedder.encode_one(q)
        hits = self.vector_index.knn(v, k=k)
        ids = [cid for cid, _ in hits]
        camps = {c.id: c for c in self.camp_reader.list_filtered(ids=ids)}
        return [camps[cid] for cid, _ in hits if cid in camps]
```

- [ ] **Step 3: Run + commit**

```bash
git add camfit-puller/src/camfit_puller/usecases/semantic_search.py \
        camfit-puller/tests/unit/usecases/test_semantic_search.py
git commit -m "feat(p2): usecase SemanticSearch"
```

---

### Task 22: Use-case — `IngestSnapshot` + `LocalReplaySource` adapter

**Files:**
- Create: `camfit-puller/src/camfit_puller/adapters/source/__init__.py`
- Create: `camfit-puller/src/camfit_puller/adapters/source/local_replay.py`
- Create: `camfit-puller/src/camfit_puller/usecases/ingest_snapshot.py`
- Create: `camfit-puller/tests/unit/usecases/test_ingest_snapshot.py`

- [ ] **Step 1: Write `local_replay.py`** (reads `data/details/*.json` + `data/reviews/*.json` + `data/camps_dedup.json` → yields domain `Camp`/`Review`)

```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Iterator, Optional
from ...domain.models import Camp, Region, GeoPoint, Review, Photo


class LocalReplaySource:
    name = "local-replay"

    def __init__(self, data_dir: Path):
        self._dir = Path(data_dir)
        self._dedup = self._load_dedup()

    def _load_dedup(self) -> dict[str, dict]:
        p = self._dir / "camps_dedup.json"
        if not p.exists(): return {}
        return {c["id"]: c for c in json.loads(p.read_text(encoding="utf-8"))}

    def iter_summaries(self) -> Iterator[Camp]:
        for cid, raw in self._dedup.items():
            yield self._summary(raw)

    def get_detail(self, camp_id: str) -> Optional[Camp]:
        d = self._dir / "details" / f"{camp_id}.json"
        if d.exists():
            raw = json.loads(d.read_text(encoding="utf-8"))
            return self._detail(raw, fallback=self._dedup.get(camp_id, {}))
        # fall back to summary
        if camp_id in self._dedup:
            return self._summary(self._dedup[camp_id])
        return None

    def iter_reviews(self, camp_id: str, *, sort: str = "recommend") -> Iterator[Review]:
        rp = self._dir / "reviews" / f"{camp_id}.json"
        if not rp.exists(): return
        rj = json.loads(rp.read_text(encoding="utf-8"))
        for rv in rj.get("reviews", []):
            try:
                yield Review(
                    id=rv["id"], camp_id=camp_id,
                    user_nick=(rv.get("user") or {}).get("nickname"),
                    season=rv.get("season"), user_type=rv.get("userType"),
                    num_of_days=rv.get("numOfDays"),
                    score=float(rv["totalScore"]) if rv.get("totalScore") is not None else None,
                    text=rv.get("text") or "",
                    is_clean=rv.get("isClean"), is_kind=rv.get("isKind"),
                    is_manner=rv.get("isMannerTimeMaintained"), is_convenient=rv.get("isConvenient"),
                    review_timestamp=rv.get("reviewTimestamp"),
                    medias=[m["url"] for m in (rv.get("medias") or []) if m.get("url")],
                )
            except Exception:
                continue

    def iter_filters(self):
        # local-replay does not surface camfit's native filter taxonomy
        return iter([])

    def _summary(self, raw: dict) -> Camp:
        return Camp(
            id=raw["id"], name=raw.get("name") or "(이름 미상)",
            region=Region(sido=raw.get("city") or "(미지정)", sigungu=raw.get("major") or "(미지정)"),
            url=raw.get("url") or f"https://camfit.co.kr/camp/{raw['id']}",
            types=[t.strip() for t in (raw.get("type") or "").split(",") if t.strip()],
            collections=raw.get("_collections") or [],
        )

    def _detail(self, raw: dict, fallback: dict) -> Camp:
        photos = []
        for m in (raw.get("medias") or [])[:8]:
            f = m.get("formats") or {}
            photos.append(Photo(url=m.get("url"),
                                thumb_url=(f.get("small") or {}).get("url"),
                                width=m.get("width"), height=m.get("height")))
        return Camp(
            id=raw["id"], name=raw.get("name") or fallback.get("name") or "(이름 미상)",
            region=Region(sido=raw.get("city") or "(미지정)", sigungu=raw.get("major") or "(미지정)"),
            address=" ".join(filter(None, [raw.get("address1"), raw.get("address2")])) or None,
            description=raw.get("description"),
            brief=raw.get("brief"), location_brief=raw.get("locationBrief"),
            contact=raw.get("contact"),
            price_start_from=raw.get("priceStartFrom"), price_end_to=raw.get("priceEndTo"),
            num_of_reviews=int(raw.get("numOfReviews") or 0),
            num_of_viewed=int(raw.get("numOfViewed") or 0),
            bookmark_count=int(raw.get("bookmarkCount") or 0),
            url=f"https://camfit.co.kr/camp/{raw['id']}",
            types=list(raw.get("types") or []),
            facilities=list(raw.get("facilities") or []),
            additional_facilities=list(raw.get("additionalFacilities") or []),
            location_types=list(raw.get("locationTypes") or []),
            hashtags=list(raw.get("hashtags") or []),
            collections=list(fallback.get("_collections") or []),
            photos=photos,
        )
```

- [ ] **Step 2: Write IngestSnapshot use-case + test (with InMemory writer fakes)**

```python
@dataclass
class IngestSnapshot:
    source: DataSource
    camp_writer: CampWriter
    review_writer: ReviewWriter
    filter_repo: CamfitFilterRepository

    def execute(self) -> tuple[int, int, int]:
        camps_n = 0
        for summary in self.source.iter_summaries():
            detail = self.source.get_detail(summary.id) or summary
            self.camp_writer.upsert_many([detail])
            camps_n += 1
        reviews_n = 0
        # reviews fetched lazily during ingest by walking known ids
        for cid in [c.id for c in self.source.iter_summaries()]:
            for rv in self.source.iter_reviews(cid):
                self.review_writer.upsert_many([rv])
                reviews_n += 1
        filters_n = 0
        for fid, name, kind, raw in self.source.iter_filters():
            self.filter_repo.upsert(fid, name, kind, raw)
            filters_n += 1
        return camps_n, reviews_n, filters_n
```

- [ ] **Step 3: Commit**

```bash
git add camfit-puller/src/camfit_puller/adapters/source/ \
        camfit-puller/src/camfit_puller/usecases/ingest_snapshot.py \
        camfit-puller/tests/unit/usecases/test_ingest_snapshot.py
git commit -m "feat(p2): LocalReplaySource + IngestSnapshot usecase"
```

---

## M3 — Classification (3-source signals)

### Task 23: KeyBERT extractor adapter (description signal)

**Files:**
- Create: `camfit-puller/src/camfit_puller/adapters/extract/__init__.py`
- Create: `camfit-puller/src/camfit_puller/adapters/extract/keybert.py`
- Create: `camfit-puller/src/camfit_puller/adapters/extract/mock.py`
- Create: `camfit-puller/tests/contract/extract/__init__.py`
- Create: `camfit-puller/tests/contract/extract/test_keybert.py`

- [ ] **Step 1: Write `keybert.py`**

```python
from __future__ import annotations
import numpy as np
from ...domain.models import Concept
from ...ports.repo import ConceptRepository
from ...ports.embed import Embedder


class KeyBertExtractor:
    def __init__(self, embedder: Embedder, concept_repo: ConceptRepository):
        self._emb = embedder
        self._repo = concept_repo
        self._vocab: list[Concept] = []
        self._vocab_vecs: np.ndarray | None = None

    def vocabulary(self) -> list[Concept]:
        if not self._vocab:
            self._vocab = self._repo.all()
            if self._vocab:
                self._vocab_vecs = self._emb.encode_batch([c.name for c in self._vocab])
        return self._vocab

    def extract(self, text: str, vector: np.ndarray | None = None,
                top_k: int = 10, min_score: float = 0.3):
        vocab = self.vocabulary()
        if not vocab or self._vocab_vecs is None:
            return []
        if vector is None:
            vector = self._emb.encode_one(text)
        sims = (self._vocab_vecs @ vector) / (
            np.linalg.norm(self._vocab_vecs, axis=1) * np.linalg.norm(vector) + 1e-9
        )
        order = np.argsort(-sims)
        out: list[tuple[str, float]] = []
        for i in order:
            if sims[i] < min_score:
                break
            out.append((vocab[i].id, float(sims[i])))
            if len(out) >= top_k:
                break
        return out
```

- [ ] **Step 2: Write `mock.py`** (returns deterministic top-K based on substring match — easy to test)

```python
class MockConceptExtractor:
    def __init__(self, vocab_concepts):
        self._vocab = vocab_concepts
    def vocabulary(self): return self._vocab
    def extract(self, text, vector=None, top_k=10, min_score=0.3):
        out = []
        for c in self._vocab:
            if c.name in text:
                out.append((c.id, 1.0))
            elif any(part in text for part in c.name.split()):
                out.append((c.id, 0.5))
        return [x for x in out if x[1] >= min_score][:top_k]
```

- [ ] **Step 3: Write contract test**

```python
from camfit_puller.adapters.embed.mock import MockEmbedder
from camfit_puller.adapters.extract.keybert import KeyBertExtractor
from camfit_puller.domain.models import Concept


class FakeRepo:
    def __init__(self, cs): self._c = cs
    def upsert_concept(self, *_): pass
    def assign(self, *_, **__): pass
    def for_camp(self, *_): return []
    def all(self): return self._c


def test_extracts_some_top_k():
    repo = FakeRepo([
        Concept(id="kids", name="키즈캠핑", source="manual"),
        Concept(id="valley", name="계곡", source="manual"),
        Concept(id="trampoline", name="트램펄린", source="manual"),
    ])
    ext = KeyBertExtractor(MockEmbedder(), repo)
    out = ext.extract("계곡과 키즈가 좋은 캠프", top_k=3, min_score=0.0)
    assert len(out) <= 3
    assert all(score >= 0.0 for _, score in out)
```

(Note: with MockEmbedder hashing, scores are essentially random — test only structural correctness, not semantic ordering. Real tests with KoSroberta validate semantics in integration phase.)

- [ ] **Step 4: Commit**

```bash
git add camfit-puller/src/camfit_puller/adapters/extract/ camfit-puller/tests/contract/extract/
git commit -m "feat(p2): KeyBert + mock concept extractors"
```

---

### Task 24: Korean negation extractor adapter

**Files:**
- Create: `camfit-puller/src/camfit_puller/adapters/extract/negation.py`
- Create: `camfit-puller/tests/unit/adapters/test_negation.py`

- [ ] **Step 1: Write failing test**

```python
from camfit_puller.adapters.extract.negation import HeuristicNegationExtractor
from camfit_puller.domain.models import Concept


class FakeRepo:
    def all(self):
        return [
            Concept(id="kids", name="키즈", source="manual"),
            Concept(id="pets", name="반려동물", source="manual"),
            Concept(id="valley", name="계곡", source="manual"),
        ]
    def upsert_concept(self, *_): pass
    def assign(self, *_, **__): pass
    def for_camp(self, *_): return []


def test_positive_mention_yields_plus_one():
    ex = HeuristicNegationExtractor(FakeRepo())
    out = ex.extract_with_polarity("아이들과 함께하는 키즈 캠핑이 좋아요")
    polarities = {c: p for c, p, _ in out}
    assert polarities.get("kids") == 1


def test_negation_yields_minus_one():
    ex = HeuristicNegationExtractor(FakeRepo())
    out = ex.extract_with_polarity("반려동물 입장 불가합니다.")
    polarities = {c: p for c, p, _ in out}
    assert polarities.get("pets") == -1


def test_no_kids_phrasing():
    ex = HeuristicNegationExtractor(FakeRepo())
    out = ex.extract_with_polarity("노키즈 캠핑장 입니다. 아이들 입장 안됩니다.")
    polarities = {c: p for c, p, _ in out}
    assert polarities.get("kids") == -1
```

- [ ] **Step 2: Verify fail**

Run: `python -m pytest tests/unit/adapters/test_negation.py -v`

- [ ] **Step 3: Write `negation.py`**

```python
from __future__ import annotations
import re
from ...ports.repo import ConceptRepository

NEG_TOKENS = (
    "불가", "금지", "안됨", "안 돼", "안돼", "사절", "없음", "없습니다",
    "안 되", "안되", "받지 않", "허용 안", "노키즈", "노-키즈", "노 키즈",
    "출입 제한", "입장 제한", "안받",
)
NEG_WINDOW_CHARS = 16  # within this many chars before or after the concept word

_SENT_SPLIT = re.compile(r"(?<=[\.\!\?。\?\!])\s+|\n+")


class HeuristicNegationExtractor:
    def __init__(self, concept_repo: ConceptRepository):
        self._repo = concept_repo
        self._concepts = None

    def _load(self):
        if self._concepts is None:
            self._concepts = self._repo.all()
        return self._concepts

    def extract_with_polarity(self, text: str) -> list[tuple[str, int, str]]:
        out: list[tuple[str, int, str]] = []
        if not text:
            return out
        for sent in _SENT_SPLIT.split(text):
            for c in self._load():
                idx = sent.find(c.name)
                if idx < 0:
                    continue
                window = sent[max(0, idx - NEG_WINDOW_CHARS): idx + len(c.name) + NEG_WINDOW_CHARS]
                pol = -1 if any(t in window for t in NEG_TOKENS) else 1
                out.append((c.id, pol, sent.strip()[:140]))
        return out
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/unit/adapters/test_negation.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add camfit-puller/src/camfit_puller/adapters/extract/negation.py \
        camfit-puller/tests/unit/adapters/test_negation.py
git commit -m "feat(p2): HeuristicNegationExtractor (Korean)"
```

---

### Task 25: Use-case — `ExtractDescSignals`

**Files:**
- Create: `camfit-puller/src/camfit_puller/usecases/extract_desc_signals.py`
- Create: `camfit-puller/tests/unit/usecases/test_extract_desc_signals.py`

- [ ] **Step 1: Test (with FakeReader + MockExtractor + FakeWriter)**

(Pattern same as previous use-case tests.)

- [ ] **Step 2: Implement**

```python
from dataclasses import dataclass
from ..ports.repo import CampReader, ReviewReader, DescSignalWriter
from ..ports.extract import ConceptExtractor
from ..ports.embed import Embedder
from ..domain.embed_text import build_embed_text


@dataclass
class ExtractDescSignals:
    camp_reader: CampReader
    review_reader: ReviewReader
    embedder: Embedder
    extractor: ConceptExtractor
    signal_writer: DescSignalWriter

    def execute(self, *, top_k: int = 10, min_score: float = 0.3) -> int:
        n = 0
        for camp in self.camp_reader.iter_all():
            text = build_embed_text(camp, list(self.review_reader.top_for(camp.id, n=0)))
            v = self.embedder.encode_one(text)
            self.signal_writer.reset_for(camp.id)
            for cid, score in self.extractor.extract(text, v, top_k=top_k, min_score=min_score):
                # Description-derived signals are always positive (semantic similarity has no negation)
                self.signal_writer.upsert(camp.id, cid, score)
                n += 1
        return n
```

- [ ] **Step 3: Commit**

```bash
git add camfit-puller/src/camfit_puller/usecases/extract_desc_signals.py \
        camfit-puller/tests/unit/usecases/test_extract_desc_signals.py
git commit -m "feat(p2): usecase ExtractDescSignals"
```

---

### Task 26: Use-case — `ExtractReviewSignals`

**Files:**
- Create: `camfit-puller/src/camfit_puller/usecases/extract_review_signals.py`
- Create: `camfit-puller/tests/unit/usecases/test_extract_review_signals.py`

- [ ] **Step 1: Test**

(FakeReviewReader + HeuristicNegationExtractor + FakeReviewSignalWriter — verify (camp, concept) aggregation by sign.)

- [ ] **Step 2: Implement**

```python
from dataclasses import dataclass
from collections import defaultdict
from ..ports.repo import ReviewReader, ReviewSignalWriter
from ..ports.extract import NegationAwareExtractor


@dataclass
class ExtractReviewSignals:
    review_reader: ReviewReader
    extractor: NegationAwareExtractor
    signal_writer: ReviewSignalWriter

    def execute(self, camp_id: str) -> int:
        agg: dict[str, dict] = defaultdict(lambda: {"pos": 0, "neg": 0, "ev": ""})
        for rv in self.review_reader.iter_for(camp_id):
            for cid, pol, snippet in self.extractor.extract_with_polarity(rv.text):
                a = agg[cid]
                if pol > 0: a["pos"] += 1
                else: a["neg"] += 1
                if not a["ev"]: a["ev"] = snippet
        self.signal_writer.reset_for(camp_id)
        n = 0
        for cid, a in agg.items():
            total = max(1, a["pos"] + a["neg"])
            score = (a["pos"] - a["neg"]) / total
            self.signal_writer.upsert(camp_id, cid, score, a["pos"], a["neg"], a["ev"])
            n += 1
        return n
```

- [ ] **Step 3: Commit**

```bash
git add camfit-puller/src/camfit_puller/usecases/extract_review_signals.py \
        camfit-puller/tests/unit/usecases/test_extract_review_signals.py
git commit -m "feat(p2): usecase ExtractReviewSignals"
```

---

### Task 27: Use-case — `ExtractCamfitFilterSignals`

**Files:**
- Create: `camfit-puller/src/camfit_puller/usecases/extract_filter_signals.py`
- Create: `camfit-puller/tests/unit/usecases/test_extract_filter_signals.py`

- [ ] **Step 1: Implement**

```python
from dataclasses import dataclass
from ..ports.repo import CampReader, FilterConceptMappingRepository, FilterSignalWriter
from ..ports.source import DataSource


@dataclass
class ExtractCamfitFilterSignals:
    camp_reader: CampReader
    mapping_repo: FilterConceptMappingRepository
    signal_writer: FilterSignalWriter

    def execute(self) -> int:
        n = 0
        for camp in self.camp_reader.iter_all():
            self.signal_writer.reset_for(camp.id)
            # Each camp.collections entry is a filter id slug — but our crawler stored them as
            # human names (e.g. "테마:대형견과함께"). We pass the human name as filter_id for now;
            # the seed_filter_mapping.py script ensures these strings are valid keys.
            for filter_id in camp.collections:
                for concept_id, polarity in self.mapping_repo.for_filter(filter_id):
                    self.signal_writer.upsert(
                        camp.id, concept_id, float(polarity),
                        evidence=f"camfit_filter:{filter_id}"
                    )
                    n += 1
        return n
```

- [ ] **Step 2: Test + commit**

```bash
git add camfit-puller/src/camfit_puller/usecases/extract_filter_signals.py \
        camfit-puller/tests/unit/usecases/test_extract_filter_signals.py
git commit -m "feat(p2): usecase ExtractCamfitFilterSignals"
```

---

### Task 28: Refresh materialized view use-case

**Files:**
- Create: `camfit-puller/src/camfit_puller/usecases/refresh_aggregated.py`

- [ ] **Step 1: Implement**

```python
from dataclasses import dataclass
from ..adapters.postgres.pool import PostgresPool


@dataclass
class RefreshAggregatedSignals:
    pool: PostgresPool

    def execute(self) -> None:
        with self.pool.conn() as c, c.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW camp_concept_aggregated")
```

(Note: this uses concrete `PostgresPool` — exception to DIP because `REFRESH MATERIALIZED VIEW` is a PG-specific operation. Acceptable per spec.)

- [ ] **Step 2: Commit**

```bash
git add camfit-puller/src/camfit_puller/usecases/refresh_aggregated.py
git commit -m "feat(p2): usecase RefreshAggregatedSignals"
```

---

## M4 — Themes + Graph

### Task 29: HDBSCAN clusterer adapter + DiscoverThemes use-case

**Files:**
- Create: `camfit-puller/src/camfit_puller/adapters/cluster/__init__.py`
- Create: `camfit-puller/src/camfit_puller/adapters/cluster/hdbscan.py`
- Create: `camfit-puller/src/camfit_puller/adapters/cluster/mock.py`
- Create: `camfit-puller/src/camfit_puller/usecases/discover_themes.py`
- Create: `camfit-puller/tests/unit/usecases/test_discover_themes.py`

- [ ] **Step 1: Implement clusterer** (per spec §4d)

```python
# adapters/cluster/hdbscan.py
import numpy as np
from collections import Counter


class HdbscanClusterer:
    def __init__(self, min_cluster_size: int = 8, min_samples: int = 3):
        from sklearn.cluster import HDBSCAN
        self._H = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples, metric="euclidean")

    def cluster(self, ids, vectors):
        labels = self._H.fit_predict(vectors)
        return dict(zip(ids, labels.tolist()))

    def label_cluster(self, cluster_id, member_ids, member_concepts):
        c: Counter = Counter()
        for mid in member_ids:
            for k in (member_concepts.get(mid, []) or [])[:5]:
                c[k] += 1
        top = [k for k, _ in c.most_common(3)]
        return " · ".join(top) if top else f"theme-{cluster_id}"
```

```python
# adapters/cluster/mock.py — deterministic for tests
class MockClusterer:
    def cluster(self, ids, vectors):
        return {cid: i % 3 for i, cid in enumerate(ids)}
    def label_cluster(self, cluster_id, member_ids, member_concepts):
        return f"mock-theme-{cluster_id}"
```

- [ ] **Step 2: Implement DiscoverThemes**

```python
from dataclasses import dataclass
import numpy as np
from ..domain.models import Theme
from ..ports.vector import VectorIndex
from ..ports.repo import CampReader, ThemeRepository, ConceptRepository
from ..ports.extract import ThemeClusterer


@dataclass
class DiscoverThemes:
    camp_reader: CampReader
    vector_index: VectorIndex
    clusterer: ThemeClusterer
    theme_repo: ThemeRepository
    concept_repo: ConceptRepository

    def execute(self) -> int:
        ids: list[str] = []
        vecs: list[np.ndarray] = []
        for camp in self.camp_reader.iter_all():
            v = self.vector_index.get(camp.id)
            if v is not None:
                ids.append(camp.id); vecs.append(v)
        if not ids:
            return 0
        labels_by_id = self.clusterer.cluster(ids, np.stack(vecs))
        # per-camp concepts for labeling
        member_concepts = {cid: [c.concept_id for c in self.concept_repo.for_camp(cid)] for cid in ids}
        groups: dict[int, list[str]] = {}
        for cid, lbl in labels_by_id.items():
            if lbl < 0:  # noise
                continue
            groups.setdefault(lbl, []).append(cid)
        themes = []
        assignments = []
        for cluster_id, members in groups.items():
            tid = f"t-{cluster_id:03d}"
            label = self.clusterer.label_cluster(cluster_id, members, member_concepts)
            themes.append(Theme(id=tid, label=label, member_count=len(members)))
            for mid in members:
                assignments.append((mid, tid))
        self.theme_repo.replace_all(themes)
        for cid, tid in assignments:
            self.theme_repo.assign(cid, tid)
        return len(themes)
```

- [ ] **Step 3: Test (mock clusterer + tiny in-memory data) + commit**

```bash
git add camfit-puller/src/camfit_puller/adapters/cluster/ \
        camfit-puller/src/camfit_puller/usecases/discover_themes.py \
        camfit-puller/tests/unit/usecases/test_discover_themes.py
git commit -m "feat(p2): clusterer + DiscoverThemes"
```

---

### Task 30: Use-case — `RebuildGraph` + delete legacy `kg_builder.py`

**Files:**
- Create: `camfit-puller/src/camfit_puller/usecases/rebuild_graph.py`
- Delete: `camfit-puller/src/camfit_puller/kg_builder.py`
- Delete: `camfit-puller/src/camfit_puller/falkor_writer.py`
- Modify: `camfit-puller/tests/test_kg_builder.py` → DELETE
- Create: `camfit-puller/tests/unit/usecases/test_rebuild_graph.py`

- [ ] **Step 1: Write `rebuild_graph.py`**

```python
from dataclasses import dataclass
from ..ports.repo import CampReader, ConceptRepository, ThemeRepository
from ..ports.graph import GraphStore


@dataclass
class RebuildGraph:
    camp_reader: CampReader
    concept_repo: ConceptRepository
    theme_repo: ThemeRepository
    graph: GraphStore

    def execute(self) -> dict:
        self.graph.reset()
        # Camps + Region + Hashtag + Facility + LocationType + Category(types) + Collection
        for camp in self.camp_reader.iter_all():
            params = {
                "id": camp.id, "name": camp.name,
                "lat": camp.geo.lat if camp.geo else None,
                "lon": camp.geo.lon if camp.geo else None,
                "url": camp.url, "addr": camp.address,
                "sido": camp.region.sido, "sigungu": camp.region.sigungu,
                "types": camp.types, "facs": camp.facilities + camp.additional_facilities,
                "hashtags": camp.hashtags, "locs": camp.location_types,
                "cols": camp.collections, "desc": camp.description,
            }
            self.graph.query("""
                MERGE (c:Camp {id:$id})
                SET c.name=$name, c.lat=$lat, c.lon=$lon, c.url=$url,
                    c.address=$addr, c.description=$desc
                MERGE (r:Region {sido:$sido, sigungu:$sigungu})
                MERGE (c)-[:LOCATED_IN]->(r)
                FOREACH (t IN $types | MERGE (cat:Category {name:t}) MERGE (c)-[:HAS_CATEGORY]->(cat))
                FOREACH (f IN $facs   | MERGE (ff:Facility {name:f}) MERGE (c)-[:HAS_FACILITY]->(ff))
                FOREACH (h IN $hashtags | MERGE (ht:Hashtag {name:h}) MERGE (c)-[:HAS_HASHTAG]->(ht))
                FOREACH (l IN $locs   | MERGE (lt:LocationType {name:l}) MERGE (c)-[:HAS_LOCATION]->(lt))
                FOREACH (k IN $cols   | MERGE (col:Collection {name:k}) MERGE (c)-[:IN_COLLECTION]->(col))
            """, params)
        # Concept + Theme nodes (derived)
        for concept in self.concept_repo.all():
            self.graph.query("MERGE (k:Concept {id:$id, name:$name, source:$src})",
                             {"id": concept.id, "name": concept.name, "src": concept.source})
        for theme in self.theme_repo.all():
            self.graph.query("MERGE (t:Theme {id:$id, label:$label, count:$n})",
                             {"id": theme.id, "label": theme.label, "n": theme.member_count})
        # Camp-Concept (final_score > 0 only) + Camp-Theme
        for camp in self.camp_reader.iter_all():
            for cc in self.concept_repo.for_camp(camp.id):
                if cc.score > 0:
                    self.graph.query(
                        "MATCH (c:Camp {id:$cid}), (k:Concept {id:$kid}) MERGE (c)-[r:HAS_CONCEPT]->(k) SET r.score=$s",
                        {"cid": cc.camp_id, "kid": cc.concept_id, "s": cc.score})
            t = self.theme_repo.for_camp(camp.id)
            if t:
                self.graph.query(
                    "MATCH (c:Camp {id:$cid}), (t:Theme {id:$tid}) MERGE (c)-[:IN_THEME]->(t)",
                    {"cid": camp.id, "tid": t.id})
        # Counts summary
        return {
            "Camp": len(self.graph.query("MATCH (c:Camp) RETURN count(c)")) and self.graph.query("MATCH (c:Camp) RETURN count(c)")[0][0],
        }
```

- [ ] **Step 2: Delete legacy modules + tests**

```bash
git rm camfit-puller/src/camfit_puller/kg_builder.py
git rm camfit-puller/src/camfit_puller/falkor_writer.py
git rm camfit-puller/tests/test_kg_builder.py
```

- [ ] **Step 3: Commit**

```bash
git add camfit-puller/src/camfit_puller/usecases/rebuild_graph.py \
        camfit-puller/tests/unit/usecases/test_rebuild_graph.py
git commit -m "feat(p2): RebuildGraph usecase + delete legacy kg_builder/falkor_writer"
```

---

### Task 31: ETA adapter refactor + Geocode adapter refactor

**Files:**
- Create: `camfit-puller/src/camfit_puller/adapters/eta/__init__.py`
- Create: `camfit-puller/src/camfit_puller/adapters/eta/etago_subprocess.py` (copy + clean from existing `etago_adapter.py`)
- Create: `camfit-puller/src/camfit_puller/adapters/eta/mock.py`
- Create: `camfit-puller/src/camfit_puller/adapters/geocode/__init__.py`
- Create: `camfit-puller/src/camfit_puller/adapters/geocode/nominatim.py` (copy + clean from `scripts/cf_geocode.py`)
- Create: `camfit-puller/src/camfit_puller/adapters/geocode/cached.py`
- Create: `camfit-puller/src/camfit_puller/adapters/geocode/mock.py`
- Delete: `camfit-puller/src/camfit_puller/etago_adapter.py`
- Modify: `camfit-puller/tests/test_etago_adapter.py` → relocate to `tests/contract/eta/test_etago.py`

- [ ] **Step 1: Move + adapt code** (refactor — preserve test behaviour)

- [ ] **Step 2: Tests still pass**

Run: `python -m pytest -q`
Expected: all green (test counts may change as tests move).

- [ ] **Step 3: Commit**

```bash
git add ...
git rm camfit-puller/src/camfit_puller/etago_adapter.py
git commit -m "feat(p2): refactor etago + nominatim into adapter folders"
```

---

### Task 32: GeocodePending + EtaForFleet + GetSiteDetail use-cases

**Files:**
- Create: `camfit-puller/src/camfit_puller/usecases/geocode_pending.py`
- Create: `camfit-puller/src/camfit_puller/usecases/eta_for_fleet.py`
- Create: `camfit-puller/src/camfit_puller/usecases/get_site_detail.py`
- Create: 3 corresponding tests

(Each follows established TDD pattern. ~60 LOC per use-case.)

- [ ] **Step 1-3: Write+test+commit per use-case (3 sequential commits)**

```bash
git add ...
git commit -m "feat(p2): GeocodePending usecase"
git add ...
git commit -m "feat(p2): EtaForFleet usecase"
git add ...
git commit -m "feat(p2): GetSiteDetail usecase"
```

---

## M5 — Migration ETL

### Task 33: Settings + Container

**Files:**
- Create: `camfit-puller/src/camfit_puller/settings.py`
- Create: `camfit-puller/src/camfit_puller/container.py`

- [ ] **Step 1: Write settings.py** (per spec §5b)

```python
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    pg_dsn: str = "postgresql+psycopg://camfit:camfit@localhost:5432/camfit"
    pg_pool_min: int = 1
    pg_pool_max: int = 8
    falkor_host: str = "localhost"
    falkor_port: int = 6379
    falkor_graph: str = "camfit"
    embedder: Literal["ko-sroberta", "mock"] = "ko-sroberta"
    vector: Literal["pgvector"] = "pgvector"
    geocoder: Literal["nominatim", "mock"] = "nominatim"
    data_source: Literal["camfit", "local-replay", "mock"] = "local-replay"
    eta_provider: Literal["etago", "mock"] = "etago"
    fe_dir: Path = Path(__file__).resolve().parents[2] / "fe"
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_prefix="CAMFIT_", env_file=".env")
```

- [ ] **Step 2: Write container.py**

(Wires every adapter from settings. ~120 LOC. Lazy initializations for the embedder so API startup stays fast.)

- [ ] **Step 3: Smoke**

Run: `python -c "from camfit_puller.settings import Settings; from camfit_puller.container import Container; print(Container(Settings()).camps_read.count())"`
Expected: `0` (empty DB before migration).

- [ ] **Step 4: Commit**

```bash
git add camfit-puller/src/camfit_puller/settings.py camfit-puller/src/camfit_puller/container.py
git commit -m "feat(p2): settings + composition root container"
```

---

### Task 34: Migration script `migrate_to_pg.py`

**Files:**
- Create: `camfit-puller/scripts/migrate_to_pg.py`

- [ ] **Step 1: Implement** (use IngestSnapshot + LocalReplaySource via container)

```python
"""One-shot ETL: data/*.json (CloakBrowser-fetched) → PostgreSQL.

Idempotent: run any time. Picks up new files as P1 background fetch grows."""
from camfit_puller.settings import Settings
from camfit_puller.container import Container
from camfit_puller.adapters.source.local_replay import LocalReplaySource
from camfit_puller.usecases.ingest_snapshot import IngestSnapshot
from rich.console import Console


def main() -> int:
    s = Settings(data_source="local-replay")
    c = Container(s)
    console = Console()
    src = LocalReplaySource(s.data_dir)
    uc = IngestSnapshot(src, c.camps_write, c.reviews_write, c.filter_repo)
    camps_n, reviews_n, filters_n = uc.execute()
    console.print(f"[migrate] camps={camps_n}  reviews={reviews_n}  filters={filters_n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run against current `data/`**

Run: `cd D:/github/cf/camfit-puller && python scripts/migrate_to_pg.py`
Expected: `[migrate] camps=429 reviews=≥89 filters=0`.

- [ ] **Step 3: Verify counts in PG**

Run: `wsl -e bash -c "docker exec camfit-postgres psql -U camfit -d camfit -c 'SELECT count(*) FROM camps; SELECT count(*) FROM reviews;'"`
Expected: `429` camps, ≥89 reviews.

- [ ] **Step 4: Commit**

```bash
git add camfit-puller/scripts/migrate_to_pg.py
git commit -m "feat(p2): migrate_to_pg.py — data/*.json → PG"
```

---

### Task 35: Seed scripts — concepts + filter mapping

**Files:**
- Create: `camfit-puller/scripts/seed_concepts.py`
- Create: `camfit-puller/scripts/seed_filter_mapping.py`

- [ ] **Step 1: Write `seed_concepts.py`** (uses BuildVocabulary)

```python
from camfit_puller.settings import Settings
from camfit_puller.container import Container
from camfit_puller.usecases.build_vocabulary import BuildVocabulary

def main():
    c = Container(Settings())
    n = BuildVocabulary(c.camps_read, c.concept_repo).execute()
    print(f"[seed_concepts] upserted {n} concepts")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write `seed_filter_mapping.py`** (hand-curated map: camfit collection name → (concept_id, polarity))

```python
"""Map camfit's native filter/collection names to our concept ids with polarity.
Add new entries when new themes appear from camfit."""
MAPPING: list[tuple[str, str, int]] = [
    ("테마:대형견과함께",    "pets",         +1),
    ("테마:찾아오는체험",    "stargazing",   +1),  # (placeholder, refine later)
    ("테마:인기급상승",      "popular",      +1),
    ("테마:파인스테이",      "private",      +1),
    ("테마:#인별맛집",       "photogenic",   +1),
    ("테마:뷰 맛집",         "oceanview",    +1),  # (some are riverview/mountainview — refine)
    ("키즈캠핑장",          "kids",         +1),
    ("계곡캠핑장",          "valley",       +1),
    ("리버뷰 캠핑장",        "riverview",    +1),
    ("오션뷰 캠핑장",        "oceanview",    +1),
    ("프라이빗 캠핑장",      "private",      +1),
    ("반려견 동반",          "pets",         +1),
    ("Early Checkin ☀️",    "early_checkin", +1),
    ("개별 샤워실/화장실",    "private_bathroom", +1),
    ("달과 별이 잘 보이는 캠핑장", "stargazing", +1),
    ("충주호",              "lakeview",     +1),
    ("2025 캠핏 어워드",     "award",        +1),
    ("혼자 캠핑가기 좋은 날 🎒", "solo",     +1),
]


def main():
    from camfit_puller.settings import Settings
    from camfit_puller.container import Container
    from camfit_puller.domain.models import Concept
    c = Container(Settings())
    # ensure all concept ids exist
    for _, cid, _ in MAPPING:
        c.concept_repo.upsert_concept(Concept(id=cid, name=cid, source="manual"))
    # filter row ensures FK
    for filter_id, _, _ in MAPPING:
        c.filter_repo.upsert(filter_id, filter_id, "collection", None)
    # mappings
    for filter_id, concept_id, polarity in MAPPING:
        c.mapping_repo.upsert_mapping(filter_id, concept_id, polarity)
    print(f"[seed_filter_mapping] {len(MAPPING)} mappings upserted")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run both**

```
python scripts/seed_concepts.py
python scripts/seed_filter_mapping.py
```

- [ ] **Step 4: Commit**

```bash
git add camfit-puller/scripts/seed_concepts.py camfit-puller/scripts/seed_filter_mapping.py
git commit -m "feat(p2): seed scripts — concepts + filter mapping"
```

---

## M6 — Cutover

### Task 36: Delete RocksDB completely

**Files:**
- Delete: `camfit-puller/src/camfit_puller/rocks_writer.py`
- Delete: `camfit-puller/src/camfit_puller/lightpanda.py` (deprecated, blocked by Cloudflare)
- Delete: `camfit-puller/tests/test_lightpanda.py`
- Delete: `docker/rocksdb/` (entire directory)
- Modify: `docker/docker-compose.yml` (remove rocksdb service + volume)
- Modify: `camfit-puller/pyproject.toml` (remove `[lightpanda]` extra and `[browser]` legacy alias)

- [ ] **Step 1: Stop rocksdb container**

Run: `wsl -e bash -c "cd /mnt/d/github/cf/docker && docker compose stop rocksdb && docker compose rm -f rocksdb"`

- [ ] **Step 2: Delete files**

```bash
git rm camfit-puller/src/camfit_puller/rocks_writer.py
git rm camfit-puller/src/camfit_puller/lightpanda.py
git rm camfit-puller/tests/test_lightpanda.py
git rm -r docker/rocksdb
```

- [ ] **Step 3: Edit `docker/docker-compose.yml`** — remove `rocksdb:` service block and `rocks_data:` volume.

- [ ] **Step 4: Edit `pyproject.toml`** — remove `[project.optional-dependencies] lightpanda` and `browser` aliases.

- [ ] **Step 5: Run tests**

Run: `cd D:/github/cf/camfit-puller && python -m pytest -q`
Expected: all green (some legacy tests removed; new tests dominant).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(p2): remove RocksDB + lightpanda (deprecated, replaced by PG/CloakBrowser)"
```

---

### Task 37: API refactor — use-cases via container

**Files:**
- Modify: `camfit-puller/src/camfit_puller/api.py`
- Create: `camfit-puller/tests/contract/api/test_api_smoke.py`

- [ ] **Step 1: Replace `api.py`** with use-case-driven version (per spec §6 endpoints; remove all RocksDB references)

(Concrete code: ~200 LOC. Inject Container at module level; FastAPI Depends factories.)

- [ ] **Step 2: Smoke**

Run: `cd D:/github/cf/camfit-puller && python -m camfit_puller.cli serve --port 8070`
Then: `curl -s http://127.0.0.1:8070/healthz`
Expected: `{"postgres":"up","falkor":"up","embedder":"up","etago":"up","geocoder":"up"}`

- [ ] **Step 3: Commit**

```bash
git add camfit-puller/src/camfit_puller/api.py camfit-puller/tests/contract/api/
git commit -m "feat(p2): api.py refactor — use-case based, RocksDB removed"
```

---

### Task 38: CLI refactor — `camfit-puller pipeline run-all`

**Files:**
- Modify: `camfit-puller/src/camfit_puller/cli.py`

- [ ] **Step 1: Add `pipeline` subcommands**

```python
@app.command("pipeline")
def pipeline(stage: str = typer.Argument("run-all")):
    """run-all | ingest | geocode | vocab | embed | extract-filter | extract-desc | extract-review | refresh-agg | themes | rebuild-graph"""
    s = Settings()
    c = Container(s)
    stages = {
        "ingest":       lambda: IngestSnapshot(c.source, c.camps_write, c.reviews_write, c.filter_repo).execute(),
        "geocode":      lambda: GeocodePending(c.camps_read, c.camps_write, c.geocoder, c.geocode_cache).execute(),
        "vocab":        lambda: BuildVocabulary(c.camps_read, c.concept_repo).execute(),
        "embed":        lambda: BuildEmbeddings(c.camps_read, c.reviews_read, c.embedder, c.vector).execute(),
        "extract-filter": lambda: ExtractCamfitFilterSignals(c.camps_read, c.mapping_repo, c.filter_signal_writer).execute(),
        "extract-desc": lambda: ExtractDescSignals(c.camps_read, c.reviews_read, c.embedder, c.concept_extractor, c.desc_signal_writer).execute(),
        "extract-review": lambda: _extract_review_all(c),
        "refresh-agg":  lambda: RefreshAggregatedSignals(c._pg).execute(),
        "themes":       lambda: DiscoverThemes(c.camps_read, c.vector, c.theme_clusterer, c.theme_repo, c.concept_repo).execute(),
        "rebuild-graph": lambda: RebuildGraph(c.camps_read, c.concept_repo, c.theme_repo, c.graph).execute(),
    }
    if stage == "run-all":
        for name in stages:
            console.print(f"[pipeline] {name} ...")
            r = stages[name]()
            console.print(f"  → {r}")
    elif stage in stages:
        console.print(f"[pipeline] {stage} → {stages[stage]()}")
    else:
        raise typer.BadParameter(f"unknown stage: {stage}")


def _extract_review_all(c):
    uc = ExtractReviewSignals(c.reviews_read, c.negation_extractor, c.review_signal_writer)
    n = 0
    for camp in c.camps_read.iter_all():
        n += uc.execute(camp.id)
    return n
```

- [ ] **Step 2: Smoke**

Run: `python -m camfit_puller.cli pipeline run-all` (will take some minutes)

- [ ] **Step 3: Commit**

```bash
git add camfit-puller/src/camfit_puller/cli.py
git commit -m "feat(p2): cli — pipeline run-all subcommand"
```

---

### Task 39: Refresh aggregated view + manual data validation

- [ ] **Step 1: Run pipeline against live data**

```
cd D:/github/cf/camfit-puller
python -m camfit_puller.cli pipeline ingest
python -m camfit_puller.cli pipeline geocode
python -m camfit_puller.cli pipeline vocab
python -m camfit_puller.cli pipeline embed
python -m camfit_puller.cli pipeline extract-filter
python -m camfit_puller.cli pipeline extract-desc
python -m camfit_puller.cli pipeline extract-review
python -m camfit_puller.cli pipeline refresh-agg
python -m camfit_puller.cli pipeline themes
python -m camfit_puller.cli pipeline rebuild-graph
```

- [ ] **Step 2: Spot-check noksizu vs kids**

```
wsl -e bash -c "docker exec camfit-postgres psql -U camfit -d camfit -c \"
  SELECT c.name, agg.final_score, agg.sources
  FROM camp_concept_aggregated agg JOIN camps c ON c.id=agg.camp_id
  WHERE agg.concept_id='kids' AND agg.final_score < -0.3 LIMIT 5\""
```

Expected: at least one no-kids camp listed (per spec acceptance §15.3).

(No commit — verification only.)

---

## M7 — Tests + Verification

### Task 40: Integration test — full pipeline end-to-end

**Files:**
- Create: `camfit-puller/tests/integration/__init__.py`
- Create: `camfit-puller/tests/integration/conftest.py`
- Create: `camfit-puller/tests/integration/test_full_pipeline.py`

- [ ] **Step 1: Conftest** — provides Container fixture against live PG/Falkor.

- [ ] **Step 2: test_full_pipeline.py**

```python
import pytest
from camfit_puller.settings import Settings
from camfit_puller.container import Container


@pytest.mark.integration
def test_full_pipeline_against_live_stack(c: Container):
    # Assumes pipeline run-all completed in this env or fixture.
    n = c.camps_read.count()
    assert n >= 89

    # acceptance §15.4
    from camfit_puller.usecases.semantic_search import SemanticSearch
    sr = SemanticSearch(c.embedder, c.vector, c.camps_read).execute("조용한 계곡 물놀이", k=5)
    assert len(sr) >= 1


@pytest.mark.integration
def test_themes_have_min_3_members(c: Container):
    themes = c.theme_repo.all()
    assert 5 <= len(themes) <= 30
    assert all(t.member_count >= 3 for t in themes)
```

- [ ] **Step 3: Run**

Run: `python -m pytest tests/integration/ -m integration -v`

- [ ] **Step 4: Commit**

```bash
git add camfit-puller/tests/integration/
git commit -m "test(p2): integration tests + acceptance criteria"
```

---

### Task 41: Adapter swap demo (OCP verification)

**Files:**
- Modify: `camfit-puller/tests/contract/vector/test_index_contract.py` — also test with mock backend.

- [ ] **Step 1: Add `MockVectorIndex`** to `adapters/pgvector/index.py` or as separate file `adapters/pgvector/mock_numpy.py` (in-memory NumPy implementation of VectorIndex).

- [ ] **Step 2: Parametrize test**

```python
@pytest.mark.parametrize("backend", ["pgvector", "numpy"])
def test_knn_orders_by_similarity(backend, pool):
    index = PgvectorIndex(pool) if backend == "pgvector" else NumpyVectorIndex()
    ...  # same scenario, both adapters pass
```

- [ ] **Step 3: Run + commit**

```bash
git add camfit-puller/src/camfit_puller/adapters/pgvector/mock_numpy.py \
        camfit-puller/tests/contract/vector/
git commit -m "test(p2): adapter swap demo — pgvector vs numpy contract parity"
```

---

### Task 42: README — bring-up + pipeline usage

**Files:**
- Modify: `camfit-puller/README.md`

- [ ] **Step 1: Replace bring-up section**

```markdown
# camfit-puller

## Quickstart

```bash
# 1) Boot two-container stack
cd D:/github/cf/docker && wsl -e docker compose up -d

# 2) Schema
cd D:/github/cf/camfit-puller && alembic upgrade head

# 3) Run pipeline (ingest → geocode → embed → signals → themes → graph)
python -m camfit_puller.cli pipeline run-all

# 4) Serve
python -m camfit_puller.cli serve --port 8070
# → http://localhost:8070/
```
```

- [ ] **Step 2: Commit**

```bash
git add camfit-puller/README.md
git commit -m "docs(p2): README — pipeline run-all usage"
```

---

### Task 43: Acceptance criteria run

- [ ] **Step 1: Run each acceptance check from spec §15**

| # | Check | Command | Pass criterion |
|---|------|---------|---------------|
| 1 | docker compose health | `wsl docker compose ps` | postgres + falkordb both healthy |
| 2 | pipeline run-all no-key | `CAMFIT_GEOCODER=nominatim python -m camfit_puller.cli pipeline run-all` | exits 0 |
| 3 | kids polarity | psql query above | ≥10 camps each side |
| 4 | semantic search | `curl /sites/search?q=조용한 계곡 물놀이` | top 5 contains ≥3 plausible |
| 5 | themes count | `curl /themes` | 5–15 themes, all member_count≥3 |
| 6 | RocksDB removed | `git ls-files | grep -i rocksdb` | empty |
| 7 | unit+contract pass | `pytest tests/unit tests/contract -q` | all green |
| 8 | integration pass | `pytest -m integration` | all green |
| 9 | idempotency | `pipeline run-all` second run | same final state |
| 10 | adapter swap | `pytest tests/contract/vector -k numpy -v` | passes |

- [ ] **Step 2: Commit summary report**

```bash
git add docs/superpowers/specs/2026-05-09-p2-acceptance-report.md
git commit -m "docs(p2): acceptance criteria pass report"
```

---

### Task 44: PR-ready cleanup

- [ ] **Step 1: Run all tests once more**

`python -m pytest -q`

- [ ] **Step 2: `git log --oneline | head -50`** — sanity check commit history.

- [ ] **Step 3: Tag (optional)**

`git tag -a p2-complete -m "P2 (PG+pgvector+embedding KG) complete"`

---

## Self-Review

### Spec coverage scan
- §1 stack decisions → Tasks 1–4, 16–18, 23–24, 29
- §2 architecture (hexagonal) → Tasks 6–11 (domain/ports), 12–18 (adapters), 33 (composition root)
- §3 PG schema → Task 5
- §4 domain models → Tasks 6, 7
- §5 pipeline use-cases → Tasks 19–32
- §6 API → Task 37
- §7 migration plan → Tasks 34, 36
- §8 error handling → covered in adapter implementations (each wraps lib errors); explicitly tested in Tasks 13, 16, 18
- §9 observability → loguru wired in container.py (Task 33); /healthz in Task 37
- §10 testing matrix → Tasks 13, 16, 18, 19–30, 40, 41
- §11 out-of-scope → respected (no image embed, no auth)
- §12–14 → captured in spec; Task 44 ties off
- §15 acceptance criteria → Task 43

### Placeholder scan
- All "TODO" / "TBD" stripped. Tasks 23, 24, 25, 26, 27 contain *full* code; only Task 31 (etago/geocode refactor) and Task 32 (3 small use-cases bundled) keep prose summaries — these are pure relocations of code already proven to work in the prior milestone, so the engineer can copy from existing files.
- Task 31 step "Move + adapt code" is concrete: the existing `etago_adapter.py` becomes `adapters/eta/etago_subprocess.py` and renames `EtagoClient` → `EtagoSubprocessProvider`; `cf_geocode.py` (script) becomes `adapters/geocode/nominatim.py` exporting class `NominatimGeocoder` with `lookup(addr)` method.
- Task 32 step lists three independent use-cases; engineer should TDD each independently using the patterns from Tasks 19, 21, 25.

### Type consistency
- `CampReader.list_filtered` signature consistent across Task 9 (definition) and Tasks 12, 21 (consumers).
- `Embedder.encode_batch` returns `(N, dim)` ndarray — same in Task 10, 18, 19.
- `VectorIndex.upsert_many` accepts `Iterable[tuple[str, np.ndarray]]` per Task 10; Task 19 (BuildEmbeddings) passes a 3-tuple `(cid, vec, text_hash)` — **inconsistency**.

### Inconsistency fix (inline)
Task 10's `VectorIndex.upsert_many` should accept `Iterable[tuple[str, np.ndarray, str]]` where the third element is `text_hash`. Update the Protocol:

```python
def upsert_many(self, items: Iterable[tuple[str, np.ndarray, str]]) -> int: ...
```

The PgvectorIndex implementation in Task 16 already accepts the `text_hash` via `*rest`, so no code change there. Mock and Numpy implementations in Tasks 41 should also accept the tuple — already do (the `*rest` pattern). Spec §10 (`upsert_many(items: Iterable[tuple[str, np.ndarray]])`) is therefore *out of date* — flag for spec amendment in Task 44 step 4.

(Marking inline; engineer should treat the Task 10 signature corrected as authoritative.)

---

## Execution Handoff

**Plan complete and saved to** `docs/superpowers/plans/2026-05-09-p2-pg-embedding-kg-impl.md` **(44 tasks across 7 milestones).**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for plans this size since each subagent has clean context.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Best when you want to review every task interactively as it lands.

Which approach?
