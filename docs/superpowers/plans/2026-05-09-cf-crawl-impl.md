# cf-crawl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Lift camfit-puller's crawl logic into a sibling `cf-crawl/` package; introduce a `CanonicalRawCamp` schema; add a `thankqcamping` source; preserve the existing 1,647-camp camfit dataset and the camfit-puller P2 service.

**Architecture:** Hexagonal again — `cf-crawl/core` defines the canonical schema and Source Protocol; `cf-crawl/sources/<name>/` each implement the Protocol; convergence at `cf-data/merged.jsonl`; camfit-puller adds a `JsonlSource` adapter (replaces `LocalReplaySource` over time).

**Tech Stack:** Python 3.11+, pydantic v2, typer, httpx, **CloakBrowser** for stealth, Playwright as fallback. No new heavy deps.

**Reference spec:** `docs/superpowers/specs/2026-05-09-cf-crawl-multi-source-design.md`

**Milestones:**
- M1 (T1–T6): cf-crawl package skeleton + canonical schema + JSONL writer
- M2 (T7–T12): camfit source — lift, refactor, prove parity with current camps_dedup.json
- M3 (T13–T16): thankqcamping source — discover, fetch, parse
- M4 (T17–T20): merge + index + camfit-puller JsonlSource adapter
- M5 (T21–T24): integration tests + acceptance run + docs

**Parallelization note:** During M1–M2, the existing camfit-puller P2 service stays operational on its current `data/details/*.json + data/reviews/*.json` archive. M2's parity check ensures we don't regress.

---

## Pre-flight

- [ ] Confirm camfit-puller P2 acceptance (T39 pipeline run-all green from prior session, 101 tests passing).
- [ ] Confirm `data/camps_dedup.json` line count (today: 1,647).
- [ ] Confirm CloakBrowser still works: `wsl -e bash -c "~/.local/bin/lightpanda --help"` OR Windows: `python -c "from cloakbrowser import launch; print('ok')"`.
- [ ] Decide host: develop on `D:/github/cf/` directly, no worktree (per session convention).

---

## File structure (target)

```
cf-crawl/
├── pyproject.toml                       Task 1
├── README.md                            Task 1
├── src/
│   └── cf_crawl/
│       ├── __init__.py                  Task 1
│       ├── core/
│       │   ├── schema/
│       │   │   ├── __init__.py
│       │   │   ├── camp.py              Task 2 — CanonicalRawCamp
│       │   │   ├── review.py            Task 2 — CanonicalRawReview
│       │   │   └── photo.py             Task 2 — CanonicalRawPhoto
│       │   ├── contracts/
│       │   │   ├── __init__.py
│       │   │   └── source.py            Task 3 — Source Protocol
│       │   ├── jsonl/
│       │   │   ├── __init__.py
│       │   │   ├── writer.py            Task 4 — append-only writer
│       │   │   └── reader.py            Task 4 — streaming reader
│       │   ├── merge.py                 Task 17 — convergence step
│       │   ├── index.py                 Task 18 — manifest builder
│       │   └── utils/
│       │       ├── __init__.py
│       │       ├── stealth.py           Task 5 — UA + delay (lifted)
│       │       ├── geocode.py           Task 5 — Nominatim (lifted)
│       │       ├── retry.py             Task 5 — backoff helpers
│       │       └── dedup.py             Task 6 — canonical_id + name/addr normalize
│       ├── sources/
│       │   ├── __init__.py
│       │   ├── camfit/
│       │   │   ├── __init__.py
│       │   │   ├── README.md            Task 7 — ToS + endpoint catalogue
│       │   │   ├── fetcher.py           Task 8 — lift + refactor cf_pull_*.py
│       │   │   ├── parser.py            Task 9 — JSON shapes → CanonicalRawCamp
│       │   │   ├── engine.py            Task 10 — _collections, theme tagging
│       │   │   └── cli.py               Task 11 — `cf-crawl camfit pull` etc.
│       │   └── thankqcamping/
│       │       ├── __init__.py
│       │       ├── README.md            Task 13 — discovered endpoints + ToS
│       │       ├── fetcher.py           Task 14
│       │       ├── parser.py            Task 15
│       │       ├── engine.py            Task 16
│       │       └── cli.py               Task 16
│       └── cli.py                       Task 19 — top-level typer app
├── tests/
│   ├── unit/
│   │   ├── test_schema.py               Task 2
│   │   ├── test_jsonl.py                Task 4
│   │   ├── test_dedup.py                Task 6
│   │   └── test_camfit_parser.py        Task 9 — fixture-based
│   ├── contract/
│   │   └── test_source_protocol.py      Task 3 — every source impl satisfies
│   └── integration/
│       ├── test_camfit_pull_smoke.py    Task 12 — live, optional
│       └── test_thankqcamping_smoke.py  Task 16 — live, optional

cf-data/                                 (gitignored)
├── camfit.jsonl                         (output of T11)
├── thankqcamping.jsonl                  (output of T16)
├── merged.jsonl                         (output of T17)
└── index.json                           (output of T18)

camfit-puller/src/camfit_puller/adapters/source/jsonl.py    Task 19 — new adapter
camfit-puller/src/camfit_puller/settings.py                 Task 20 — add `jsonl_path`
```

---

## M1 — cf-crawl skeleton

### Task 1: package skeleton

**Files:**
- Create: `cf-crawl/pyproject.toml`
- Create: `cf-crawl/README.md`
- Create: `cf-crawl/src/cf_crawl/__init__.py` (empty + `__version__ = "0.1.0"`)

- [ ] **Step 1: pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cf-crawl"
version = "0.1.0"
description = "Multi-source camping-site crawler (canonical JSONL output)"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "selectolax>=0.3.21",
    "typer>=0.12",
    "pydantic>=2.7",
    "rich>=13.7",
    "tenacity>=8.2",
]

[project.optional-dependencies]
stealth = ["cloakbrowser>=0.3", "websockets>=12"]
playwright = ["playwright>=1.44"]
dev = ["pytest>=8.2", "pytest-asyncio>=0.23", "respx>=0.21"]

[project.scripts]
cf-crawl = "cf_crawl.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/cf_crawl"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: README.md** — 30-line overview pointing to spec + listing top CLI commands.

- [ ] **Step 3: install editable + smoke**
```
cd D:/github/cf/cf-crawl && pip install -e ".[dev]"
python -c "import cf_crawl; print(cf_crawl.__version__)"
```
Expected: `0.1.0`.

- [ ] **Step 4: commit**
```
cd D:/github/cf
git add cf-crawl/pyproject.toml cf-crawl/README.md cf-crawl/src/cf_crawl/__init__.py
git commit -m "feat(cf-crawl): package skeleton"
```

---

### Task 2: canonical schema (CanonicalRawCamp)

**Files:**
- Create: `cf-crawl/src/cf_crawl/core/schema/__init__.py`
- Create: `cf-crawl/src/cf_crawl/core/schema/camp.py`
- Create: `cf-crawl/src/cf_crawl/core/schema/review.py`
- Create: `cf-crawl/src/cf_crawl/core/schema/photo.py`
- Create: `cf-crawl/tests/unit/test_schema.py`

- [ ] **Step 1: write failing test**

```python
from datetime import datetime
from cf_crawl.core.schema.camp import CanonicalRawCamp
from cf_crawl.core.schema.review import CanonicalRawReview
from cf_crawl.core.schema.photo import CanonicalRawPhoto


def test_minimal_camp_validates():
    c = CanonicalRawCamp(
        source="camfit", source_id="abc", canonical_id="d3adb33f000",
        crawled_at=datetime.utcnow(), name="X",
    )
    assert c.source == "camfit"
    assert c.reviews == [] and c.photos == [] and c.raw == {}


def test_canonical_id_required():
    import pytest
    with pytest.raises(Exception):
        CanonicalRawCamp(source="x", source_id="y", crawled_at=datetime.utcnow(), name="Z")


def test_review_score_optional():
    r = CanonicalRawReview(source_id="r1", text="t")
    assert r.score is None
```

- [ ] **Step 2: implement** — exact field list per spec §3.

- [ ] **Step 3: run + commit**
```
pytest tests/unit/test_schema.py -v
git add ... && git commit -m "feat(cf-crawl): CanonicalRawCamp schema"
```

---

### Task 3: Source Protocol contract

**Files:**
- Create: `cf-crawl/src/cf_crawl/core/contracts/__init__.py`
- Create: `cf-crawl/src/cf_crawl/core/contracts/source.py`
- Create: `cf-crawl/tests/contract/test_source_protocol.py`

- [ ] **Step 1: write Protocol** per spec §4 (Source class with `name`, `discover`, `pull_all`, `pull_one`).

- [ ] **Step 2: contract test using a `MockSource`** (in-memory) that satisfies the Protocol. Verify `isinstance(MockSource(), Source)` because `runtime_checkable`.

- [ ] **Step 3: commit**
```
git commit -m "feat(cf-crawl): Source Protocol + contract test"
```

---

### Task 4: JSONL reader/writer

**Files:**
- Create: `cf-crawl/src/cf_crawl/core/jsonl/__init__.py`
- Create: `cf-crawl/src/cf_crawl/core/jsonl/writer.py`
- Create: `cf-crawl/src/cf_crawl/core/jsonl/reader.py`
- Create: `cf-crawl/tests/unit/test_jsonl.py`

- [ ] **Step 1: writer** — context manager that opens `.jsonl` for append (or truncate=True for overwrite), exposes `.write_camp(camp: CanonicalRawCamp)`, flushes after each line.

- [ ] **Step 2: reader** — generator yielding `CanonicalRawCamp` per line; tolerates malformed lines (logs + continues).

- [ ] **Step 3: roundtrip test** — write 3 camps, read 3 camps back, assert equal (compare model_dump).

- [ ] **Step 4: commit** `feat(cf-crawl): JSONL reader/writer`

---

### Task 5: Cross-cutting utils — stealth + geocode + retry

**Files:**
- Create: `cf-crawl/src/cf_crawl/core/utils/{__init__.py,stealth.py,geocode.py,retry.py}`

- [ ] **Step 1: stealth.py** — copy verbatim from `camfit-puller/src/camfit_puller/stealth.py` (the StealthClient). Adjust imports.

- [ ] **Step 2: geocode.py** — copy verbatim from `camfit-puller/scripts/cf_geocode.py` minus the FalkorDB writeback (cache uses `cf-data/geocode_cache.jsonl` via the JSONL writer). Output is `(lat, lon) | None`.

- [ ] **Step 3: retry.py** — small wrapper around `tenacity` exposing `@retry_http` decorator with sane defaults (3 attempts, 5s/15s/45s exponential).

- [ ] **Step 4: smoke + commit** `feat(cf-crawl): core utils — stealth, geocode, retry`

---

### Task 6: dedup utilities (canonical_id formula)

**Files:**
- Create: `cf-crawl/src/cf_crawl/core/utils/dedup.py`
- Create: `cf-crawl/tests/unit/test_dedup.py`

- [ ] **Step 1: write failing test**

```python
from cf_crawl.core.utils.dedup import normalize_name, normalize_addr, canonical_id


def test_normalize_drops_camping_suffix():
    assert normalize_name("원주두리 1캠핑장") == "원주두리1"


def test_normalize_lowercases():
    assert normalize_addr("강원 원주시 신림면 525") == "강원원주시신림면525"


def test_canonical_id_stable():
    a = canonical_id(name="원주두리 1캠핑장", address="강원 원주시 신림면 525")
    b = canonical_id(name="원주두리 1캠핑장 ", address="강원원주시 신림면 525")
    assert a == b


def test_canonical_id_distinct_for_different_addresses():
    a = canonical_id(name="X 캠핑장", address="강원 평창군")
    b = canonical_id(name="X 캠핑장", address="경기 가평군")
    assert a != b
```

- [ ] **Step 2: implement** per spec §5 formula.

- [ ] **Step 3: run + commit**

---

## M2 — camfit source (lift)

### Task 7: camfit source folder + README

**Files:**
- Create: `cf-crawl/src/cf_crawl/sources/camfit/{__init__.py, README.md}`

README content: ToS posture (private user research only), rate limit recommendations (≥1.5s between requests), endpoint catalogue (the same list from spec §6.1), and known-flaky areas (Cloudflare on direct API calls).

- [ ] **Step 1: write README** ~50 lines.

- [ ] **Step 2: commit** `docs(cf-crawl/camfit): README — ToS posture + endpoint catalogue`

---

### Task 8: lift fetcher.py

**Files:**
- Create: `cf-crawl/src/cf_crawl/sources/camfit/fetcher.py`

The fetcher absorbs the logic from:
- `camfit-puller/scripts/cf_pull_via_scroll.py` (collections endpoint scroll)
- `camfit-puller/scripts/cf_pull_themes.py` (per-theme pagination)
- `camfit-puller/scripts/cf_pull_details.py` (detail + reviews)
- `camfit-puller/scripts/cf_pull_expanded.py` (region/type filter clicks)

Each becomes a method of `CamfitFetcher`:
- `discover_endpoints()` — XHR sniff
- `iter_collections_page()` — paginated curations
- `iter_themes()` then `iter_camps_for_theme(theme_id)` — per-theme
- `iter_camps_for_region(sido, sigungu)` — region-filter walk
- `iter_camps_for_type(type_)` — type-filter walk
- `fetch_detail(source_id)` — `/v1/camps/{id}` capture
- `fetch_reviews(source_id, page)` — `/v1/camp/{id}/reviews`

All use CloakBrowser. The class accepts `output_dir` for any per-call snapshots and a `delay_s` policy.

- [ ] **Step 1: write the class** ~300 LOC.
- [ ] **Step 2: smoke** — instantiate, call `discover_endpoints()`. Expect non-empty endpoint list.
- [ ] **Step 3: commit** `feat(cf-crawl/camfit): fetcher (lifted from cf_pull_*.py)`

---

### Task 9: parser.py — JSON → CanonicalRawCamp

**Files:**
- Create: `cf-crawl/src/cf_crawl/sources/camfit/parser.py`
- Create: `cf-crawl/tests/unit/test_camfit_parser.py`
- Create fixture data: `cf-crawl/tests/fixtures/camfit/<sample>.json` (one summary, one detail, one reviews)

- [ ] **Step 1: capture fixtures** — extract 3 small JSON snippets from `camfit-puller/data/{camps_dedup.json|details|reviews}` into `tests/fixtures/`.

- [ ] **Step 2: write parser tests** with fixture-based assertions.

- [ ] **Step 3: implement parser** with three functions:
- `parse_summary(raw_dict) -> CanonicalRawCamp` (handles `id` vs `_id` quirk)
- `parse_detail(raw_dict) -> CanonicalRawCamp` (full fields including description, hashtags, locationTypes, facilities, photos)
- `parse_reviews(raw_dict, source_id) -> list[CanonicalRawReview]`

- [ ] **Step 4: run + commit**

---

### Task 10: engine.py — camfit-specific normalization

**Files:**
- Create: `cf-crawl/src/cf_crawl/sources/camfit/engine.py`

Engine responsibilities:
- Merge summary + detail + reviews into one `CanonicalRawCamp`.
- Compute `canonical_id` via `core.utils.dedup.canonical_id(name, address)`.
- Tag `_collections` (camfit theme/curation membership) into both `hashtags` and `raw["_collections"]`.
- Drop empty fields.

- [ ] **Step 1: implement** ~80 LOC.
- [ ] **Step 2: simple unit test** — feed a fixture, assert canonical_id is stable across re-runs.
- [ ] **Step 3: commit**

---

### Task 11: cli.py — `cf-crawl camfit <subcmd>`

**Files:**
- Create: `cf-crawl/src/cf_crawl/sources/camfit/cli.py`

Subcommands:
- `discover` — sniff endpoints, write `cf-data/camfit_endpoints.json`
- `pull` — full crawl: collections + themes + region + type. Per-camp detail + reviews. Write `cf-data/camfit.jsonl`. (~30-60 min for 1,800 camps.)
- `pull-one ID` — fetch a single camp, append/update in jsonl.
- `stats` — line count, last `crawled_at`, top sources contributing.

- [ ] **Step 1: implement** as typer sub-app (registered into top-level `cf-crawl` cli in T19).
- [ ] **Step 2: commit**

---

### Task 12: parity check — camfit.jsonl ≥ camps_dedup.json line count

- [ ] **Step 1: run** `cd D:/github/cf/cf-crawl && python -m cf_crawl camfit pull --out ../cf-data/camfit.jsonl`
- [ ] **Step 2: compare**
```
wc -l cf-data/camfit.jsonl              # expect ≥1,647
python -c "import json; d=json.load(open('camfit-puller/data/camps_dedup.json')); print(len(d))"
```
Lines should be ≥ 1,647 (current count). Stretch: 1,800.

- [ ] **Step 3: spot-check** — diff a known camp's data: same name/address/types in both files? (sample 5 random ids).
- [ ] **Step 4: commit** the verification report `docs/superpowers/specs/2026-05-09-cf-crawl-camfit-parity-report.md`.

---

## M3 — thankqcamping source

### Task 13: thankqcamping discovery

**Files:**
- Create: `cf-crawl/src/cf_crawl/sources/thankqcamping/{__init__.py, README.md}`
- Create: `cf-data/thankqcamping_inspect/r_NNN.{json,url.txt}` (output of discovery run)

- [ ] **Step 1: discovery script**

```bash
cd D:/github/cf/cf-crawl && python -m cf_crawl.sources.thankqcamping.discover \
    --base https://m.thankqcamping.com/ --out ../cf-data/thankqcamping_inspect/
```

(Implementer creates `discover.py` ad-hoc — sniff XHR, click filter chips, scroll, save.)

- [ ] **Step 2: write README** with discovered endpoints, rate limits, ToS posture (must read site's terms).

- [ ] **Step 3: commit** `feat(cf-crawl/thankqcamping): discovery + README`

---

### Task 14: thankqcamping fetcher.py

Mirrors camfit's fetcher pattern. Methods adapted to thankqcamping's actual endpoints (depends on Task 13 findings).

- [ ] Implement minimal pull flow.
- [ ] Smoke against live site (small sample, e.g. 5 camps).
- [ ] Commit.

---

### Task 15: thankqcamping parser.py + fixtures

- [ ] Capture 3 sample JSON responses (or HTML if site is server-rendered) into `tests/fixtures/thankqcamping/`.
- [ ] Write fixture-based parser tests.
- [ ] Implement parser converting site's shape → `CanonicalRawCamp`.
- [ ] Commit.

---

### Task 16: thankqcamping engine + CLI

- [ ] `engine.py` — site-specific normalizations (likely review score 0-5 → 0-100, etc.)
- [ ] `cli.py` — subcommands: `discover`, `pull`, `stats`.
- [ ] Smoke pull a small sample (50 camps).
- [ ] Commit `feat(cf-crawl/thankqcamping): engine + cli + smoke pull (N camps)`.

---

## M4 — Convergence + camfit-puller integration

### Task 17: merge.py

**Files:**
- Create: `cf-crawl/src/cf_crawl/core/merge.py`
- Create: `cf-crawl/tests/unit/test_merge.py`

Merge algorithm per spec §5:
- Read all input JSONL files.
- Group by `canonical_id`.
- Per group: union lists, prefer longer text, track `_sources`.

- [ ] **Step 1: tests** — synthetic 2-source merge with overlap; verify single output row, sources tracked.
- [ ] **Step 2: implement**.
- [ ] **Step 3: real run** — `cf-crawl merge --inputs cf-data/camfit.jsonl,cf-data/thankqcamping.jsonl --out cf-data/merged.jsonl`.
- [ ] **Step 4: commit**

---

### Task 18: index.py — manifest builder

**Files:**
- Create: `cf-crawl/src/cf_crawl/core/index.py`

Walks `cf-data/*.jsonl`, builds `cf-data/index.json` with `{canonical_id: [(source, source_id), ...], ...}`. Tracks crawl recency per canonical_id.

- [ ] **Step 1: implement + simple test**.
- [ ] **Step 2: real run** — emit `cf-data/index.json`. Verify N entries equal merged.jsonl line count.
- [ ] **Step 3: commit**

---

### Task 19: top-level CLI + camfit-puller JsonlSource

**Files:**
- Create: `cf-crawl/src/cf_crawl/cli.py` — registers source sub-apps (camfit, thankqcamping) + global `merge`, `status`, `geocode`.
- Create: `camfit-puller/src/camfit_puller/adapters/source/jsonl.py` — implements `DataSource` against a `cf-data/*.jsonl` file.
- Modify: `camfit-puller/src/camfit_puller/settings.py` — add `jsonl_path` setting.
- Modify: `camfit-puller/src/camfit_puller/container.py` — when `data_source="jsonl"`, instantiate `JsonlSource(self.settings.jsonl_path)`.

- [ ] **Step 1: top-level CLI** + smoke `cf-crawl --help`.
- [ ] **Step 2: JsonlSource adapter** — read each `CanonicalRawCamp` from JSONL, convert to `domain.Camp`.
- [ ] **Step 3: tests** — JsonlSource against a 5-row JSONL fixture.
- [ ] **Step 4: container** — wire `CAMFIT_DATA_SOURCE=jsonl` to JsonlSource.
- [ ] **Step 5: commits** (3 — cf-crawl cli, JsonlSource, container wiring)

---

### Task 20: camfit-puller settings + migration script update

- [ ] Update `migrate_to_pg.py` to read `cf-data/merged.jsonl` if env `CAMFIT_DATA_SOURCE=jsonl`. Falls back to `local-replay` otherwise.
- [ ] Run end-to-end: `cf-crawl pull camfit + thankqcamping → merge → migrate_to_pg → pipeline run-all`.
- [ ] Verify: PG `camps.count()` ≥ 1,647 (camfit alone) + thankqcamping count.
- [ ] Commit.

---

## M5 — Tests + acceptance

### Task 21: integration test — full multi-source flow

**Files:**
- Create: `cf-crawl/tests/integration/test_multi_source_e2e.py`

(Optional / live; gated by `--integration` pytest flag.)

Test flow: pull both sources (small samples) → merge → load into a test PG instance via testcontainers → assert end-to-end query works.

---

### Task 22: contract test parametrized over both sources

`cf-crawl/tests/contract/test_source_protocol.py` extended to parametrize over `CamfitSource` and `ThankqcampingSource`. Both must pass:
- discover() returns SourceManifest with non-empty `endpoints`.
- pull_all(since=None) yields ≥1 CanonicalRawCamp.
- canonical_id present and stable.

---

### Task 23: README + handoff doc

**Files:**
- Update: `cf-crawl/README.md` — full usage examples once both sources are working.
- Create: `docs/superpowers/specs/2026-05-09-cf-crawl-handoff.md` — final architecture diagram + how to add a third source.

---

### Task 24: acceptance run + commit final report

- [ ] Run all of spec §13 acceptance criteria, document results.
- [ ] Commit `docs(cf-crawl): acceptance report`.

---

## Self-review

### Spec coverage
- §2 architecture → Tasks 1, 19
- §3 schema → Task 2
- §4 source contract → Task 3
- §5 canonical_id + merge → Tasks 6, 17
- §6 sources → Tasks 7-12 (camfit), 13-16 (thankqcamping)
- §7 engine → Tasks 10, 16
- §8 utils → Task 5
- §9 CLI → Tasks 11, 16, 19
- §10 camfit-puller integration → Task 19
- §11 layout → Task 1
- §12 migration → Task 12 (camfit lift) + Task 20 (consumer wiring)
- §13 acceptance → Task 24
- §14 risks → addressed via per-source READMEs and contract tests
- §15 decisions → captured in spec; plan inherits

### Placeholder scan
None. Every task names files, gives commands, and shows expected outcomes.

### Type consistency
- `CanonicalRawCamp` / `CanonicalRawReview` / `CanonicalRawPhoto` defined in T2; referenced consistently in T9, T15, T17, T19.
- `Source` Protocol from T3 referenced in T8/14, T22.

### Open items
- thankqcamping discovery (T13) is genuinely TBD until run — plan accommodates by leaving fetcher logic flexible.
- `canonical_id` collisions: tracked but not actively resolved in this plan; future task.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-09-cf-crawl-impl.md` (24 tasks across 5 milestones).**

Per user direction in this revision: **docs only — no code execution this round.** When the user is ready to implement, launch with one of:
1. **Subagent-Driven** — fresh subagent per task + 2-stage review
2. **Inline Execution** — batch with checkpoints

Implementation is gated on user approval to start.
