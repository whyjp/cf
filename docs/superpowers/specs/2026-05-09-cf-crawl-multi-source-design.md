# cf-crawl — Multi-Source Crawler Decoupling (Design Spec)

- **Date**: 2026-05-09
- **Project**: cf (mono-repo root)
- **Sub-project**: **cf-crawl** (NEW package, separate from camfit-puller)
- **Status**: Design spec only — no code in this revision per user direction.
- **Predecessors**:
  - `2026-05-09-p2-pg-embedding-kg-design.md` (P2 hexagonal data layer)
  - `2026-05-09-p2-addendum-filter-dimensions.md` (5 filter dimensions)
- **Author**: cxx_2 + Claude

---

## 0. Why this spec

The P2 hexagonal architecture treats *data source* as a port (`ports/source.py`'s `DataSource`) — but the *crawler* itself currently lives in `camfit-puller/scripts/cf_*.py` as a tangle of one-off scripts coupled to camfit's specific endpoints, CloakBrowser browser tooling, and Korean-Cloudflare bypass logistics. 

Adding a second source (e.g., **thankqcamping** at `m.thankqcamping.com`) reveals that *crawling* is its own bounded subsystem — it has different concerns (browser stealth, anti-bot bypass, pagination logic, retry policies) than *data classification + viewing*. Mixing them into one package forces the camfit-puller package to carry browser stack dependencies even when running purely offline (e.g., the FE serving an existing PG).

This spec proposes:

1. **Lift the crawler into a sibling package `cf-crawl/`** at the repo root.
2. **Decouple source-specific raw fetch** (per-site adapters: `camfit/`, `thankqcamping/`, future `…/`) **from raw-to-domain conversion** (a thin `cf-crawl-core` library that defines the canonical raw data shape).
3. **Standardize the canonical raw output** — a JSON-Lines file format every source converges to. `camfit-puller`'s `LocalReplaySource` becomes `cf-crawl-core`'s `JsonlSource` + a `data-source-name` field.
4. **Allow source-specific processing engines**: each source can tag, normalize, or enrich raw rows differently. The merge happens at the canonical-shape boundary, not earlier.
5. **Keep camfit-puller as the data classification + viewer service** — it consumes converged JSONL, knows nothing about how the data was obtained.

Result: cleanly separable concerns. New crawler sources are isolated from the consumer; the consumer doesn't need browser tooling installed.

---

## 1. Scope

**In scope (this spec):**
- Top-level package layout `cf-crawl/`.
- A canonical raw-camp JSONL schema all sources emit.
- Per-source adapter contract (interface + per-source folder).
- Initial concrete sources: `camfit` (lift from existing) and `thankqcamping` (new).
- Convergence point and merge semantics.
- Migration plan from current `camfit-puller/scripts/cf_*.py`.
- Out-of-band utilities (geocode, retry, dedup).

**Out of scope:**
- Implementation code (this is a docs-only spec — see §15 plan tasks for sequencing).
- New downstream features in camfit-puller (those continue per their own specs).
- Image/photo download (we keep `medias[*].url` only — viewer fetches lazily from CDN).
- Real-time refresh / streaming (snapshot-based; manual rerun).
- License/contract resolution per site (each source documents its ToS posture; the user is responsible for compliance).

---

## 2. High-level architecture

```
┌──────────────────────────────────────────────────────────────┐
│  cf/                                                         │
│  ├── cf-crawl/                       ← NEW package           │
│  │     core/                                                 │
│  │       schema/                     canonical raw types     │
│  │       contracts/                  Source/Engine ports     │
│  │       jsonl/                      reader/writer + merge   │
│  │     sources/                                              │
│  │       camfit/                     lift from camfit-puller │
│  │       thankqcamping/              NEW                     │
│  │       <future-source>/                                    │
│  │     scripts/                      cli runners             │
│  │     pyproject.toml                                        │
│  │                                                           │
│  ├── cf-data/                        ← canonical JSONL store │
│  │     camfit.jsonl                                          │
│  │     thankqcamping.jsonl                                   │
│  │     merged.jsonl                  union dedup'd           │
│  │     index.json                    per-id source manifest  │
│  │                                                           │
│  ├── camfit-puller/                  ← existing, slimmed     │
│  │     (P2 service: PG, embeddings, FE — consumes cf-data/   │
│  │      JSONL via LocalReplaySource pointed at jsonl file)   │
│  │                                                           │
│  └── etago/                          ← existing, untouched   │
└──────────────────────────────────────────────────────────────┘
```

The flow:

```
[per source]  CloakBrowser/Playwright
     │
     ▼
sources/<name>/fetcher.py     — raw HTTP/JSON capture
sources/<name>/parser.py      — site-specific JSON → CanonicalRawCamp
sources/<name>/engine.py      — site-specific normalization
     │
     ▼  (writes JSONL)
cf-data/<name>.jsonl          — canonical raw (one source's snapshot)
     │
     ▼  (cf-crawl merge command)
cf-data/merged.jsonl          — union dedup'd (id-keyed)
     │
     ▼  (camfit-puller's LocalReplaySource pointed at merged.jsonl)
camfit-puller/scripts/migrate_to_pg.py
     │
     ▼
PG + FalkorDB + pgvector → API → FE
```

Source independence: deleting a sources/<name>/ subdir, or running a single source in isolation, must always be valid. The canonical-shape boundary (CanonicalRawCamp) is the only contract between crawl and viewer.

---

## 3. Canonical raw schema

Every source emits a stream of `CanonicalRawCamp` records. This is **richer** than `domain.models.Camp` — it carries source-specific extras, raw fields, and provenance, so downstream consumers (e.g., camfit-puller's IngestSnapshot) can choose which fields matter.

`cf_crawl.core.schema.CanonicalRawCamp`:

```python
class CanonicalRawCamp(BaseModel):
    # ── Identity ─────────────────────────────────────────────
    source: str                            # "camfit" | "thankqcamping" | …
    source_id: str                         # the id assigned by that source
    canonical_id: str                      # global merge key — see §5
    crawled_at: datetime
    
    # ── Core fields (every source provides these) ──────────
    name: str
    region_sido: Optional[str] = None
    region_sigungu: Optional[str] = None
    address: Optional[str] = None
    url: Optional[str] = None
    
    # ── Optional structured data ─────────────────────────
    description: Optional[str] = None
    brief: Optional[str] = None
    types: list[str] = []                  # site's vocabulary; not normalized here
    facilities: list[str] = []             # site's vocabulary
    hashtags: list[str] = []
    location_types: list[str] = []         # mountain/valley/sea — site's vocabulary
    
    # ── Source-specific raw extras ───────────────────────
    raw: dict = {}                         # opaque dict — preserved verbatim
    
    # ── Reviews (zero or more) ───────────────────────────
    reviews: list[CanonicalRawReview] = []
    
    # ── Photos ───────────────────────────────────────────
    photos: list[CanonicalRawPhoto] = []


class CanonicalRawReview(BaseModel):
    source_id: str                         # review id from source
    user_nick: Optional[str] = None
    text: str
    score: Optional[float] = None          # 0-100; site rescales as needed
    season: Optional[str] = None
    user_type: Optional[str] = None
    review_timestamp: Optional[int] = None
    medias: list[str] = []                 # url list


class CanonicalRawPhoto(BaseModel):
    url: str
    thumb_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    caption: Optional[str] = None
```

JSONL line format: one `CanonicalRawCamp` per line, UTF-8.

---

## 4. Source contract

Per-source folder layout:

```
cf-crawl/sources/<name>/
  __init__.py
  fetcher.py    — async/sync HTTP + browser tooling, returns raw JSON pages
  parser.py     — site JSON → CanonicalRawCamp objects
  engine.py     — site-specific dedup/normalize (e.g., camfit's _id↔id rewriting)
  cli.py        — typer subcommand `cf-crawl camfit pull`
  README.md     — site-specific notes (ToS posture, endpoint catalogue, gotchas)
```

Each source MUST implement `cf_crawl.core.contracts.Source`:

```python
class Source(Protocol):
    name: str                              # canonical source slug
    
    def discover(self) -> SourceManifest: ...
    """Returns metadata about endpoints discovered, last-known camp count,
    and any auth/cookie state that must be preserved between fetcher invocations."""
    
    def pull_all(self, *, since: datetime | None = None) -> Iterator[CanonicalRawCamp]: ...
    """Yield every camp on the site. `since` allows incremental fetch (skip
    camps unchanged since timestamp). For first crawl, `since=None`."""
    
    def pull_one(self, source_id: str) -> Optional[CanonicalRawCamp]: ...
    """Refresh a single camp's detail + reviews. Used for targeted updates."""
```

Optional source-specific extension methods (only declared on the source's own class):

- `pull_taxonomy() -> list[Filter]` — for sources with explicit category trees (camfit's themes/collections fall here)
- `attach_marketing(camp, raw)` — site-specific tagging beyond what the parser does (camfit's `_collections` field)

These are not part of the `Source` Protocol — keeps the contract narrow.

---

## 5. Convergence: `canonical_id` and merge semantics

Each source has a stable `source_id` that's *globally unique within that source*. We need a **cross-source merge key** so a camp listed on both camfit and thankqcamping isn't double-counted.

Strategy (MVP):

```
canonical_id = sha1(normalize(name) + ":" + normalize(address))[:16]
              if address else
              sha1("source:" + source + ":" + source_id)[:16]
```

- `normalize(name)`: lowercase, strip whitespace, drop "캠핑장" suffix, drop punctuation.
- `normalize(address)`: lowercase, drop spaces, keep digits.

This is **non-perfect** — camps with the same name in the same region collide, and camps where one source has an address and the other doesn't collide weakly. We deliberately accept this trade-off for v1; future improvement is geo-distance + name fuzzy matching (Levenshtein) for refinement.

Merge semantics in `cf-crawl merge`:

1. Read every `cf-data/<name>.jsonl`.
2. Group by `canonical_id`.
3. For each group:
   - **Pick the source-of-truth values per field** by precedence: longer text wins for `description`/`brief`; non-null wins for scalars; **lists union and dedup**.
   - Merge `reviews[*]` by review's `source_id` namespaced as `(source, source_id)` — all reviews preserved.
   - Merge `photos[*]` similarly.
   - Track the source list in `_sources: list[str]`.
4. Emit `cf-data/merged.jsonl` — one canonical row per `canonical_id`.
5. Emit `cf-data/index.json`: a manifest mapping `canonical_id → [(source, source_id), ...]` for traceability.

camfit-puller's `LocalReplaySource` reads `merged.jsonl` (configurable). `Camp.id` becomes `canonical_id`. `Camp.collections` aggregates source-specific tags.

---

## 6. Initial sources

### 6.1 `camfit` source — lift from existing camfit-puller

**Endpoints currently used** (P1 history):
- `/v1/collections?key=search&skip=N&limit=5` — curation lists
- `/v1/themes?skip=N&limit=10` + `/v1/themes/{id}/camps?skip=N&limit=10` — per-theme listings
- `/v1/camps/{id}` — full detail
- `/v1/camp/{id}/reviews?page=N&pageSize=N` — reviews
- region/type filter chips — yields more lists (per recent expansion to 1,647 camps)

Migration: each `camfit-puller/scripts/cf_*.py` script becomes a method or function in `cf-crawl/sources/camfit/fetcher.py`. The CLI surface becomes `cf-crawl camfit <subcommand>`.

camfit's quirk: 89 entries use `id`, 340 use `_id` (encountered in T22). The parser handles both; canonical_id flattens.

### 6.2 `thankqcamping` source — NEW (mobile UX)

URL: `https://m.thankqcamping.com/`

**Discovery TODO** (during impl phase):
- Inspect mobile UX → likely SPA with JSON endpoints similar to camfit.
- Identify list / detail / reviews endpoints via XHR capture.
- Note: any anti-bot posture (Cloudflare? Naver-bot allowance?). 
- Document ToS posture in the source's README.

**Expected adapter shape** (assumption):
- Mobile UX implies pages like `/list?region=…&type=…`, `/detail/{id}`.
- JSON shapes will differ from camfit; parser maps to `CanonicalRawCamp`.

If discovery reveals heavily-different patterns (e.g. server-rendered HTML only), the source's `fetcher.py` adapts — the `Source` Protocol is shape-agnostic.

### 6.3 Future sources (not in this spec)

Yanolja, Goodcamping, public data (data.go.kr 한국관광공사 등) — each gets its own folder under `sources/`. The canonical contract stays.

---

## 7. Engine layer (per-source enrichment)

Each source may have a *processing engine* that transforms raw fetcher output into the canonical shape with site-specific touches:

- **camfit**: extract `_collections` (theme/category membership) into `hashtags` and `_collections`; map camfit's own filter taxonomy into `types`/`facilities`.
- **thankqcamping**: TBD (depends on discovered shape — may need different review-score normalization).

The engine is the right place for source-specific normalization (e.g., review score 0-5 → 0-100). Downstream camfit-puller assumes 0-100; engines unify to that.

If a source's data is too divergent (e.g., a public data source returns admin-only fields like 사업자번호), the engine drops fields outside the canonical schema. Nothing leaks.

---

## 8. Geocode + cross-cutting utilities

Cross-cutting tools live under `cf-crawl/core/utils/`:

- `geocode.py` — Nominatim adapter (lifted from `camfit-puller/scripts/cf_geocode.py`). Used optionally by any source's engine. Cache lives in `cf-data/geocode_cache.jsonl`.
- `dedup.py` — name+address normalization helpers (the `canonical_id` formula).
- `retry.py` — common retry/backoff for HTTP.
- `stealth.py` — UA rotation, robots.txt check (lifted from `camfit-puller/src/camfit_puller/stealth.py`).

Sources opt in to these — no inheritance, just utility function calls.

---

## 9. CLI surface

A single typer app with per-source subcommands:

```
cf-crawl --version
cf-crawl <source> discover            # find endpoints, no fetch
cf-crawl <source> pull --out=data/<source>.jsonl
cf-crawl <source> pull-one <id>       # refresh a single camp
cf-crawl <source> stats               # line count, last-fetched, etc.

cf-crawl merge --inputs=data/*.jsonl --out=data/merged.jsonl
cf-crawl status                       # all sources, line counts, freshness

cf-crawl geocode --input data/<source>.jsonl --in-place
                                       # fill geo for any source
```

`cf-crawl pull <source>` is non-blocking; long runs print progress.

---

## 10. camfit-puller integration

camfit-puller stays as the *consumer*. Two adapter changes:

### 10.1 New JsonlSource adapter

`camfit-puller/src/camfit_puller/adapters/source/jsonl.py` (NEW) — implements `ports.source.DataSource` against a `cf-data/<file>.jsonl`. Replaces the file-based parts of `LocalReplaySource`.

```python
class JsonlSource:
    name = "jsonl"
    def __init__(self, jsonl_path: Path): ...
    def iter_summaries(self) -> Iterator[Camp]: ...   # CanonicalRawCamp → domain Camp
    def get_detail(self, source_id: str) -> Optional[Camp]: ...
    def iter_reviews(self, source_id: str, *, sort) -> Iterator[Review]: ...
    def iter_filters(self) -> Iterator[tuple]: ...    # always empty for jsonl
```

### 10.2 LocalReplaySource deprecation

The old `LocalReplaySource` (reading `data/details/*.json` + `data/reviews/*.json`) becomes deprecated when cf-crawl is online; it stays for one release cycle as a fallback.

### 10.3 Settings update

```python
# settings.py
data_source: Literal["jsonl", "camfit-cloak", "local-replay", "mock"] = "jsonl"
jsonl_path: Path = Path("../cf-data/merged.jsonl")
```

---

## 11. Repository layout

```
cf/                          (mono-repo root, current location)
├── camfit-puller/           (existing P2 service — minor changes)
├── cf-crawl/                NEW
│   ├── pyproject.toml
│   ├── README.md
│   ├── src/
│   │   └── cf_crawl/
│   │       ├── __init__.py
│   │       ├── core/
│   │       │   ├── schema/
│   │       │   ├── contracts/
│   │       │   ├── jsonl/
│   │       │   └── utils/
│   │       ├── sources/
│   │       │   ├── camfit/
│   │       │   └── thankqcamping/
│   │       └── cli.py
│   └── tests/
│       ├── unit/                contract test (each source)
│       └── integration/         live fetch (gated, optional)
├── cf-data/                 NEW — canonical JSONL store (gitignored)
├── etago/                   (existing)
├── docker/                  (existing)
├── docs/                    (existing)
│   └── superpowers/
│       ├── specs/
│       │   ├── 2026-05-09-p2-pg-embedding-kg-design.md
│       │   ├── 2026-05-09-p2-addendum-filter-dimensions.md
│       │   └── 2026-05-09-cf-crawl-multi-source-design.md   ← THIS DOC
│       └── plans/
│           ├── 2026-05-09-p2-pg-embedding-kg-impl.md
│           └── 2026-05-09-cf-crawl-impl.md                  ← NEXT DOC
└── ...
```

---

## 12. Migration: camfit-puller/scripts/cf_*.py → cf-crawl/sources/camfit

The existing P1 ad-hoc scripts:
- `cf_grab.py`, `cf_inspect_api.py`, `cf_search_inspect.py`, `cf_inspect_filters.py`, `cf_inspect_detail.py`, `cf_inspect_region_filter.py`
- `cf_pull_via_scroll.py`, `cf_pull_themes.py`, `cf_pull_details.py`, `cf_pull_expanded.py`
- `cf_dedup_to_csv.py`, `cf_geocode.py`, `cf_load_rich.py`

After migration:
- All `cf_pull_*.py` and `cf_inspect_*.py` move into `cf-crawl/sources/camfit/fetcher.py` as **methods on `CamfitSource`**.
- `cf_grab.py` becomes a `cf-crawl camfit grab` smoke command.
- `cf_dedup_to_csv.py` is **deleted** — JSONL replaces CSV. (camfit-puller never needed CSV anyway.)
- `cf_geocode.py` becomes `cf-crawl/core/utils/geocode.py` — usable by any source.
- `cf_load_rich.py` is deleted — RebuildGraph use-case in P2 already does the canonical loading.

The OLD scripts stay until the new ones produce equivalent JSONL output, verified by line count matching.

---

## 13. Acceptance criteria

The implementation plan (next: `2026-05-09-cf-crawl-impl.md`) must:

1. `cf-crawl camfit pull --out cf-data/camfit.jsonl` produces ≥ N rows, where N = current `camps_dedup.json` size (1,647 today).
2. Each emitted JSONL row validates against `CanonicalRawCamp`.
3. `cf-crawl thankqcamping discover` runs successfully (at least surfaces some endpoints) — even if pull is incomplete in MVP.
4. `cf-crawl merge --inputs cf-data/camfit.jsonl,cf-data/thankqcamping.jsonl --out cf-data/merged.jsonl` produces a deduped union; line count ≤ sum of inputs (any cross-source overlap collapses).
5. `camfit-puller`'s `JsonlSource` reads `cf-data/merged.jsonl` cleanly; `migrate_to_pg.py` ingests without error.
6. End-to-end `cf-crawl pull → merge → migrate_to_pg → pipeline run-all` produces a working camfit-puller serve, FE shows merged data, source labels visible in detail panel (`_sources: ["camfit", "thankqcamping"]`).
7. Removing `cf-crawl/sources/thankqcamping/` doesn't break camfit pulls or the consumer.
8. Removing `cf-crawl/` entirely (going back to one source) doesn't break the consumer if `LocalReplaySource` fallback is kept.

---

## 14. Risks

| Risk | Mitigation |
|------|-----------|
| Per-site ToS / robots.txt — multi-source amplifies legal exposure | Each source's README documents its ToS posture explicitly. User accepts responsibility per source. |
| `canonical_id` formula collisions between camps with same name in same region | Acceptable for v1; future Levenshtein refinement on top. Track collisions in `index.json`. |
| Each source's parser fragility against site UI changes | Per-source unit/contract tests with fixture HTML/JSON. Regression detection on each crawl. |
| Single point of merge — buggy merge breaks everything | Merge step is idempotent + deterministic. `merged.jsonl` is recomputable from per-source files. |
| Heavy browser tooling (CloakBrowser, Playwright) bloating cf-crawl deps | Optional extras: `cf-crawl[stealth]` installs cloakbrowser; default install is light. |
| thankqcamping discovery may reveal a fundamentally different pattern (e.g., HTML-only) requiring more work | Plan accommodates: each source's fetcher is free-form. Spec doesn't lock in JSON-only. |

---

## 15. Decision log

| # | Decision | Rationale |
|---|---------|-----------|
| 1 | Separate `cf-crawl` package from `camfit-puller` | Crawler concerns (browser, anti-bot) are different from data viewer concerns. SOLID/SRP. |
| 2 | JSONL canonical format (not Parquet/CSV) | Streamable, human-readable, append-friendly, language-agnostic. |
| 3 | `canonical_id` = sha1(name+address) [:16] | Simple, deterministic, reasonable collision rate. Refinement deferred. |
| 4 | Per-source engine for normalization | Each site has quirks; mixing into core would create a god-class. |
| 5 | `cf-data/` is gitignored | Crawl outputs are derived data. Reproducible from source scripts. |
| 6 | camfit-puller keeps `LocalReplaySource` for one cycle | Avoids breaking old workflow during transition. |
| 7 | This is **docs-only** — no code yet | Per user direction. Implementation phased separately. |

---

## 16. Glossary

| Term | Meaning |
|------|---------|
| source | A data origin (camfit, thankqcamping, …). Each has its own folder under `cf-crawl/sources/`. |
| `source_id` | The id assigned by the source. e.g. camfit's 24-hex MongoDB ObjectId. Unique within source. |
| `canonical_id` | Cross-source merge key. Same camp on multiple sources → same canonical_id. |
| CanonicalRawCamp | The schema every source converges on. Richer than camfit-puller's `Camp` (carries raw extras). |
| Engine | Per-source normalization layer between fetcher (raw) and canonical schema. |
| Fetcher | Per-source HTTP/browser logic. The "active crawl" component. |
| Convergence | The merge step where per-source JSONL files become one. |

---

End of cf-crawl design spec.
