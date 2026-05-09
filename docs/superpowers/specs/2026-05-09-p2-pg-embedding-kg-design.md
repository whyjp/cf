# P2 — Postgres + pgvector + Embedding-Derived KG (Design Spec)

- **Date**: 2026-05-09
- **Project**: camfit-puller
- **Sub-project**: P2 (data structuring + embedding + auto concept/theme + KG enrichment)
- **Author**: cxx_2 + Claude (brainstorming session)
- **Status**: Approved (pending user spec review)
- **Predecessor**: live e2e (89 → 429 camps via CloakBrowser, RocksDB+FalkorDB+ETA prototype)
- **Successor**: P3 — Frontend overhaul (multi-view + map library swap + origin button)

---

## 0. Why this spec

The current prototype proved the live data pipeline (CloakBrowser → 429 camps → ETA filter) works. P2 turns the prototype into a **solid, swap-friendly local stack** by:

1. Replacing RocksDB with **PostgreSQL + pgvector** as a single relational+vector truth.
2. Introducing **3-source category signals** (camfit native filter / description embedding / review entity extraction with Korean negation) — fixes the *"노키즈 캠핑장 → 키즈캠핑장 오분류"* bug and removes hardcoded `has_valley/has_kids/has_trampoline` columns.
3. Building an **autonomous concept + theme pipeline** on top of local Korean sentence-transformers (no API key, no external dependency).
4. Wiring the codebase into **Hexagonal (Ports & Adapters) architecture** so any concrete tech (vector store, geocoder, data source, embedder) can be swapped via env config without touching use-case code.
5. Keeping FalkorDB as a *derived* graph view, always rebuildable from PG. (Decided: FalkorDB stays — separate agent's viewer depends on it.)

---

## 1. Stack decisions (locked)

| Slot | Choice | Reason |
|------|--------|--------|
| Relational + vector | **PostgreSQL 16 + pgvector** | Single-file truth, KNN built in |
| Graph | **FalkorDB** | Fixed by external viewer compat |
| Embedder | **sentence-transformers `jhgan/ko-sroberta-multitask`** (768d) | No API key, CPU-OK |
| Concept extractor | **KeyBERT-style cosine + Korean negation rules** | Reproducible, no LLM dep |
| Theme clusterer | **HDBSCAN** (`sklearn.cluster.HDBSCAN`) | Density-based; tolerates noise |
| Geocoder | **Nominatim + on-disk cache** | Free, no key, ToS 1 req/sec |
| Data source | **CamfitSource (CloakBrowser)** | Established working flow |
| ETA | **etago subprocess** | Existing |
| RocksDB | **REMOVED** | Redundant once PG arrives. User-approved: no deprecation grace period — delete on cutover |

Env-driven swap: `CAMFIT_VECTOR=pgvector|numpy|faiss`, `CAMFIT_EMBEDDER=ko-sroberta|e5|mock`, `CAMFIT_DATA_SOURCE=camfit|local-replay|mock` etc.

---

## 2. Architecture (hexagonal)

```
┌──────────────────────────────────────────────────────────┐
│ ① DOMAIN (pure pydantic)                                 │
│   Camp, Review, Concept, Theme, Region, GeoPoint,        │
│   EtaResult, errors                                      │
├──────────────────────────────────────────────────────────┤
│ ② PORTS (typing.Protocol, runtime_checkable)             │
│   CampReader/Writer, ReviewReader/Writer,                │
│   ConceptRepo, ThemeRepo, CamfitFilterRepo,              │
│   FilterConceptMappingRepo,                              │
│   VectorIndex, GraphStore,                               │
│   Embedder, ConceptExtractor, NegationAwareExtractor,    │
│   ThemeClusterer, Geocoder, DataSource, EtaProvider      │
├──────────────────────────────────────────────────────────┤
│ ③ USE-CASES (port-only depend)                           │
│   IngestSnapshot, GeocodePending, BuildVocabulary,       │
│   BuildEmbeddings, ExtractCamfitFilterSignals,           │
│   ExtractDescSignals, ExtractReviewSignals,              │
│   DiscoverThemes, RebuildGraph,                          │
│   SemanticSearch, GetSiteDetail, EtaForFleet             │
├──────────────────────────────────────────────────────────┤
│ ④ ADAPTERS                                               │
│   postgres/, pgvector/, falkor/,                         │
│   embed/(sentence-transformers, mock),                   │
│   extract/(KeyBert + heuristic-negation, tfidf, mock),   │
│   cluster/(hdbscan, kmeans, mock),                       │
│   geocode/(nominatim+cache, mock),                       │
│   source/(camfit-cloakbrowser, local-replay, mock),      │
│   eta/(etago-subprocess, mock)                           │
├──────────────────────────────────────────────────────────┤
│ ⑤ COMPOSITION ROOT                                       │
│   settings.py (pydantic-settings)                        │
│   container.py (dict-based DI; no dependency-injector)   │
│   api.py (FastAPI Depends → container.use_case())        │
│   cli.py (typer; same pattern)                           │
└──────────────────────────────────────────────────────────┘
```

SOLID enforcement:
- **SRP**: each adapter = one technology, one reason to change.
- **OCP**: new data source / vector store = adapter add + env switch; use-cases untouched.
- **LSP**: contract tests in `tests/contract/` validate any adapter pair satisfies the same scenarios.
- **ISP**: `CampReader` and `CampWriter` are separate Protocols.
- **DIP**: `usecases/` and `api.py` import only `ports/`, never `adapters/` directly.

Directory:
```
src/camfit_puller/
  domain/{models.py, errors.py, embed_text.py}
  ports/{repo.py, vector.py, graph.py, embed.py, extract.py, geocode.py, source.py, eta.py}
  usecases/{ingest_snapshot.py, build_embeddings.py, ...}
  adapters/{postgres/, pgvector/, falkor/, embed/, extract/, cluster/, geocode/, source/, eta/}
  container.py
  settings.py
  api.py
  cli.py
```

---

## 3. PostgreSQL schema

### 3.1 Core (truth)

```sql
camps (
  id text PK, name text, sido text, sigungu text, address text,
  lat double precision, lon double precision,
  brief text, location_brief text, contact text,
  price_start_from int, price_end_to int,
  num_of_reviews int DEFAULT 0,
  num_of_viewed int DEFAULT 0,
  bookmark_count int DEFAULT 0,
  url text, source text DEFAULT 'camfit',
  fetched_at timestamptz DEFAULT now(),
  geocoded_at timestamptz
);  -- NOTE: no has_valley/has_kids/has_trampoline; classification via signals/concepts.

camp_descriptions  (camp_id text PK REFERENCES camps, description text);
camp_types         (camp_id, type, PK(camp_id, type));
camp_facilities    (camp_id, facility, is_additional bool DEFAULT false, PK(camp_id, facility));
camp_hashtags      (camp_id, hashtag, PK(camp_id, hashtag));
camp_location_types(camp_id, location_type, PK(camp_id, location_type));
camp_collections   (camp_id, collection_name, PK(camp_id, collection_name));
camp_medias        (camp_id, idx, url, thumb_url, w, h, PK(camp_id, idx));

reviews (
  id text PK, camp_id text REFERENCES camps,
  user_nick text, season text, user_type text, num_of_days int,
  score numeric(5,2), text text NOT NULL,
  is_clean bool, is_kind bool, is_manner bool, is_convenient bool,
  review_timestamp bigint
);
review_medias (review_id, idx, url, PK(review_id, idx));
```

### 3.2 Camfit-native taxonomy

```sql
camfit_filters (id text PK, name text, kind text, raw jsonb);
-- kind ∈ 'theme' | 'inventory_filter' | 'badge' | 'collection'

filter_concept_mapping (
  filter_id text REFERENCES camfit_filters,
  concept_id text REFERENCES concepts,
  polarity smallint NOT NULL CHECK (polarity IN (-1, 1)),
  PK (filter_id, concept_id)
);
```

### 3.3 Concepts + 3-source signals

```sql
concepts (
  id text PK, name text NOT NULL, category text,
  description text, is_axis bool DEFAULT false
);

camp_filter_signals (camp_id, concept_id, score numeric(5,4), evidence text, PK(camp_id, concept_id));
camp_desc_signals   (camp_id, concept_id, score numeric(5,4), PK(camp_id, concept_id));
camp_review_signals (camp_id, concept_id, score numeric(5,4),
                     pos_count int DEFAULT 0, neg_count int DEFAULT 0,
                     evidence text, PK(camp_id, concept_id));

CREATE MATERIALIZED VIEW camp_concept_aggregated AS
SELECT
  camp_id, concept_id,
  COALESCE(SUM(f.score),0) * 1.0
+ COALESCE(SUM(r.score),0) * 0.7
+ COALESCE(SUM(d.score),0) * 0.5
   AS final_score,
  array_remove(ARRAY[
    CASE WHEN bool_or(f.score IS NOT NULL) THEN 'filter' END,
    CASE WHEN bool_or(r.score IS NOT NULL) THEN 'review' END,
    CASE WHEN bool_or(d.score IS NOT NULL) THEN 'description' END
  ], NULL) AS sources
FROM (
  SELECT camp_id, concept_id FROM camp_filter_signals UNION
  SELECT camp_id, concept_id FROM camp_desc_signals   UNION
  SELECT camp_id, concept_id FROM camp_review_signals
) all_sigs
LEFT JOIN camp_filter_signals f USING (camp_id, concept_id)
LEFT JOIN camp_review_signals r USING (camp_id, concept_id)
LEFT JOIN camp_desc_signals   d USING (camp_id, concept_id)
GROUP BY camp_id, concept_id;
CREATE INDEX ON camp_concept_aggregated (concept_id, final_score DESC);
```

### 3.4 Embeddings + themes

```sql
camp_embeddings (
  camp_id text PK REFERENCES camps,
  vec vector(768) NOT NULL,
  text_hash text NOT NULL,
  model_name text NOT NULL,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX ON camp_embeddings USING hnsw (vec vector_cosine_ops) WITH (m=16, ef_construction=64);

themes (
  id text PK, label text NOT NULL,
  centroid vector(768),
  member_count int DEFAULT 0,
  manual_label text,                                    -- override for poor auto-labels
  created_at timestamptz DEFAULT now()
);
camp_themes (camp_id text PK REFERENCES camps, theme_id text REFERENCES themes);
```

### 3.5 Caches

```sql
geocodes (query text PK, lat double precision, lon double precision,
          source text, raw jsonb, cached_at timestamptz DEFAULT now());

eta_cache (origin text, dest text, minutes int, source text,
           cached_at timestamptz DEFAULT now(), PK(origin, dest));
```

### 3.6 Indexes

- `camps`: B-tree on `(sido)`, `(sigungu)`. For `(lat, lon)` we use B-tree on `(lat)` + B-tree on `(lon)` for now (sufficient for bbox queries at 4000-row scale). PostGIS spatial indexes are deferred to **P3** if real spatial queries (within-radius, polygon contains) become necessary.
- `reviews`: `(camp_id)`, `(camp_id, score DESC)`
- `camp_concept_aggregated`: `(concept_id, final_score DESC)` (already shown)
- `camp_embeddings.vec`: HNSW (already shown)

---

## 4. Domain models (excerpts)

```python
class Camp(BaseModel):
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
    # NOTE: no has_valley/has_kids/has_trampoline. Classification via concepts.
```

(Full models in §3 of brainstorming transcript; copy into `domain/models.py` at impl time.)

---

## 5. Pipeline use-cases

```
IngestSnapshot          DataSource → CampWriter, ReviewWriter
GeocodePending          CampReader (where geo is null) → Geocoder → CampWriter.set_geo
                         (also sets camps.geocoded_at = now())
BuildVocabulary         CampReader hashtags + facilities + manual seed → ConceptRepository
BuildEmbeddings         build_embed_text → Embedder.encode_batch → VectorIndex.upsert_many
ExtractCamfitFilterSignals  collections → filter_concept_mapping → camp_filter_signals
ExtractDescSignals      KeyBertExtractor over description+brief → camp_desc_signals
ExtractReviewSignals    HeuristicNegationExtractor over reviews → camp_review_signals
DiscoverThemes          load embeddings → HDBSCAN → label_cluster → ThemeRepository.replace_all
RebuildGraph            PG truth → FalkorGraph.reset() + MERGE batches (Camp, Region, Hashtag,
                         Facility, LocationType, Concept, Theme + edges)
SemanticSearch          q → Embedder.encode_one → VectorIndex.knn → CampReader.list_filtered(ids)
GetSiteDetail           camp + reviews + concepts + theme + photos → API JSON
EtaForFleet             same as current
```

Each is a class with `__init__(...ports)` and `execute(...)`. All idempotent.

---

## 6. API endpoints

```
GET  /healthz                   PG/Falkor/embedder/etago/geocoder status
GET  /facets                    sido buckets + concepts (axis & non-axis) + themes counts
GET  /sites                     filter by region/concept(score)/bbox; returns Camp summaries
GET  /sites/{id}                full detail incl. photos, concepts, theme, top reviews
GET  /sites/search?q=&k=20      semantic search
GET  /sites/{id}/similar?k=10   nearest neighbors
GET  /concepts                  all concepts + counts
GET  /concepts/{name}/camps     camps where final_score > threshold
GET  /themes                    all themes
GET  /themes/{id}/camps         theme members
GET  /eta?origin&dest           single
POST /eta/batch                 batch
DELETE /eta/cache               clear
POST /admin/rebuild-graph       FalkorDB rebuild (auth optional)
POST /admin/reembed             re-run BuildEmbeddings for changed text_hash
```

Filter syntax replaces boolean axes (FastAPI parses `concept` as `list[str]`, repeatable):
- `GET /sites?concept=kids&min_score=0.3` — kids-positive (single concept)
- `GET /sites?concept=kids&max_score=-0.3` — explicitly no-kids (negative-only)
- `GET /sites?concept=valley&concept=trampoline&min_score=0.3` — *both* concepts must satisfy min_score (AND)
- For OR semantics use multiple `concepts_any=valley,trampoline` parameter (single comma-separated)
- min_score / max_score apply uniformly across the listed concepts (no per-concept threshold in v1; deferred to P3 if needed)

---

## 7. Migration plan (RocksDB → out)

```
[A] docker/postgres/ added (pgvector image: pgvector/pgvector:pg16)
[B] alembic init + revision applies §3 schema
[C] scripts/migrate_to_pg.py:
    - data/camps_dedup.json    → camps + camp_types + camp_collections
    - data/details/*.json      → camp_descriptions + facilities + hashtags
                                + location_types + medias + brief + price
    - data/reviews/*.json      → reviews + review_medias
    - data/geocode.json        → geocodes + camps.lat/lon update
    - DISTINCT (sido, sigungu) → regions
[D] scripts/seed_concepts.py + scripts/seed_filter_mapping.py
[E] cli: camfit-puller pipeline run-all
    → IngestSnapshot (already done in [C])
    → GeocodePending (idempotent, skips cached)
    → BuildVocabulary
    → BuildEmbeddings
    → ExtractCamfitFilterSignals + ExtractDescSignals + ExtractReviewSignals
    → DiscoverThemes
    → RebuildGraph
[F] DELETE RocksDB (immediate, per user approval):
    - docker compose stop rocksdb && rm
    - rm -rf docker/rocksdb/
    - delete src/camfit_puller/rocks_writer.py
    - api.py: drop ROCKS_BASE / camp:{id} / detail:{id} / reviews:{id} fetches
    - tests/: drop rocks tests
    - docker/docker-compose.yml: remove rocksdb service
[G] Tests: tests/integration/ runs full pipeline against pg+falkor (CI optional flag)
```

Background P1 (live detail fetch, currently 141/429) keeps writing to `data/details/` and `data/reviews/`; the migration ETL just re-runs whenever these grow.

---

## 8. Error handling

- Adapters wrap raw lib exceptions → domain errors (`CampNotFound`, `EmbeddingDimMismatch`, `GeocodeUnresolved`, `EtaUnavailable`, `GraphUnavailable`).
- Use-cases re-raise. FastAPI exception_handler maps to HTTPException.
- Bulk operations return `BulkResult(ok: int, failed: list[(id, err)])` — no all-or-nothing.
- All use-cases are idempotent.
- `/healthz` reports per-adapter status; `/sites` graceful-degrades (missing signals shown as 0-score).

---

## 9. Observability

- structured logs via loguru: one structured line per use-case start/end with key params.
- `/healthz` 5-component status (PG, FalkorDB, vector, embedder loaded, etago bin).
- `concept evidence` columns provide human-readable provenance — surfaced in FE tooltip.
- Optional Prometheus exporter (post-spec).

---

## 10. Testing

| Layer | Adapters | Time |
|------|---------|------|
| `tests/unit/usecases/` | InMemory*/Mock | <1s |
| `tests/contract/repo/` | InMemory + Postgres (testcontainers) | ~10s |
| `tests/contract/vector/` | Numpy + pgvector | ~5s |
| `tests/contract/embed/` | Mock + ko-sroberta | ~30s (one-time model load) |
| `tests/integration/` | full docker stack | ~minutes |

CI default: unit + contract. Integration behind `--integration` flag.

---

## 11. Out of scope

- Image embedding / photo similarity
- User accounts / bookmarks
- Real-time availability (zone reservation UI)
- Multi-tenant
- Map UI (frontend) — that is **P3**

---

## 12. Glossary

| Term | Meaning |
|------|---------|
| concept | Atomic classification axis (`kids`, `pets`, `valley`, `trampoline`, `oceanview`, ...). Stored in `concepts` table. May be marked `is_axis=true` for FE primary toggles. |
| signal | Per-camp evidence for a concept from one of three sources (filter / desc / review), with signed score. |
| theme | Emergent cluster of camps in embedding space, with auto-derived label. Each camp belongs to ≤1 theme. |
| filter (camfit native) | Camfit's own taxonomy (themes, inventory filters, badges, collections). Mapped to concepts via `filter_concept_mapping`. |
| polarity | ±1 marker on a `filter_concept_mapping` row. e.g., `노키즈캠핑장 → (kids, -1)`. |
| `final_score` | Aggregated signed score in `camp_concept_aggregated`. Positive = applies; negative = explicitly negated. |
| evidence | Human-readable snippet showing why a signal was assigned. |

---

## 13. Risks

| Risk | Mitigation |
|------|-----------|
| ko-sroberta CPU embed time on 4000+ camps | batch 32 + text cap → ~10min one-shot. GPU optional path. |
| Negation heuristic FP/FN | Evidence column lets human spot-check; future swap of NegationAwareExtractor for an NLP model is a 1-adapter change. |
| Theme labels weak | `themes.manual_label` override column. |
| Region naming changes (전북 → 전북특별자치도) | Future: `regions.gov_code` + normalization function. |
| pgvector index rebuild on schema change | Tolerable (one-shot, ~tens of seconds). |

---

## 14. Decisions log

| # | Decision | Made by | Rationale |
|---|---------|---------|-----------|
| 1 | Sub-project decomposition: P1 (live crawl, in flight) / **P2 (this spec)** / P3 (frontend) | autonomous | Scope decomposition per brainstorming-skill rules |
| 2 | Embedder: local sentence-transformers (`ko-sroberta`) | user (Q-P2.1=a) | No API key (intent §c.a) |
| 3 | Pipeline output: full (semantic search + KeyBERT concepts + clustered themes) | user (Q-P2.2=d) | Maximizes #2 + #3 from prompt |
| 4 | Storage: **PostgreSQL + pgvector + FalkorDB** (RocksDB removed) | user (Q-P2.3=c, then upgraded to PG/pgvector) | Production-grade relational + vector in one |
| 5 | Address-first geocode, no coord fallback | user (#5) | Address is the canonical truth |
| 6 | RocksDB deleted immediately, no grace period | user | Pre-1.0 dev phase, no backwards-compat concern |
| 7 | Drop hardcoded `has_valley/has_kids/has_trampoline` columns; use 3-source signal model with polarity | user | Real classification must come from camfit filter + description + review with negation |
| 8 | FalkorDB stays (not Neo4j) | user | External viewer agent depends on FalkorDB |

---

## 15. Acceptance criteria

The implementation plan (next: invoke writing-plans skill) must:

1. Boot two-container docker compose (postgres + falkordb) with `docker compose up -d` and `/healthz` returns all up.
2. End-to-end pipeline runnable via `camfit-puller pipeline run-all` with no API keys configured.
3. `/sites?concept=kids&min_score=0.3` returns kids-friendly camps; `&max_score=-0.3` returns explicit no-kids camps; both correct on hand-verified ground truth (≥10 camps each).
4. `/sites/search?q="조용한 계곡 물놀이"` returns ranked semantic matches (top-5 contain ≥3 plausible matches).
5. `/themes` returns 5–15 themes for the current 429-camp dataset; each theme has ≥3 members (HDBSCAN -1 noise filtered out).
6. RocksDB completely removed from repo + compose + tests.
7. `pytest tests/unit/ tests/contract/` passes with 0 external dep (testcontainers-pg only for repo contract).
8. `pytest tests/integration/` passes against live docker stack.
9. All use-cases idempotent (re-run produces identical state).
10. Adapter swap demo: `CAMFIT_VECTOR=numpy pytest tests/contract/vector/` passes — proves OCP.

---

End of P2 design spec.
