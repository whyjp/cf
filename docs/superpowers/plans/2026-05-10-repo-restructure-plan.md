# Repo restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split monolithic `camfit-puller/` into 4 cleanly bounded packages (`crawl/camfit/`, `crawl/txcp/`, `backend/`, `pipeline/`) under a single uv workspace, plus root `scripts/` for sh-only ops, while preserving git history and never breaking integrations between sprints.

**Architecture:** uv workspace at repo root. 4 members: 2 crawler packages (light deps), 1 backend (FastAPI + DB stack), 1 pipeline (workspace-dep on backend, orchestrates jsonl→postgres→falkor + etago geocode). Each sprint = one or more atomic git commits + full pytest "not live" PASS gate before next sprint starts.

**Tech Stack:** Python 3.11+, uv (workspace), pytest, httpx, pydantic, FastAPI, falkordb, postgres+pgvector, docker compose, bash.

**Spec:** [`docs/superpowers/specs/2026-05-10-repo-restructure-design.md`](../specs/2026-05-10-repo-restructure-design.md)

---

## Pre-flight (S0)

### Task 1: Verify clean working state

**Files:**
- Read: `git status`, `git log -1`

- [ ] **Step 1: Confirm starting commit + clean state**

```bash
cd /mnt/d/github/cf  # WSL path — Windows: D:\github\cf
git status --short | grep -v "^??" || true   # tracked changes only
git log -1 --oneline
```

Expected: HEAD at `eb1c88b feat(tkcp-crawl): ...` (or later if commits added). No tracked-modified files.

- [ ] **Step 2: Snapshot pre-state for rollback**

```bash
git tag pre-restructure-$(date +%Y%m%d) HEAD
```

Expected: tag created. Can rollback with `git reset --hard pre-restructure-YYYYMMDD`.

---

## Sprint 1 — Workspace root scaffolding

**Goal:** Create root `pyproject.toml` (workspace), `.gitignore` boost, `.run/` dir. No code moves yet.

### Task 2: Root pyproject.toml workspace

**Files:**
- Create: `pyproject.toml`
- Modify: `.gitignore` (root — may not exist; create if missing)

- [ ] **Step 1: Write root pyproject.toml**

`pyproject.toml`:
```toml
[project]
name = "cf-workspace"
version = "0.0.0"
description = "cf monorepo — crawl/{camfit,txcp} + backend + pipeline"
requires-python = ">=3.11"

[tool.uv.workspace]
members = ["crawl/txcp"]

[tool.uv.sources]
# cf-backend = { workspace = true }   # uncomment when backend/ exists (Sprint 5)
```

Note: `members` starts with only `crawl/txcp` (the existing tkcp-crawl, to be moved in Sprint 2). Members get added as dirs are created.

- [ ] **Step 2: Write/update root .gitignore**

If `.gitignore` doesn't exist at repo root, create it. If it does, append the new lines (don't duplicate).

```bash
cd /mnt/d/github/cf
test -f .gitignore && cat .gitignore || true   # inspect first
```

Append (or create) `.gitignore`:
```
# uv workspace
.venv/
__pycache__/
*.pyc

# runtime
.run/
*.pid
*.log

# pytest
.pytest_cache/
.coverage

# crawler data dirs (subdir .gitignore also covers, but root is belt+suspenders)
crawl/*/data/
```

- [ ] **Step 3: Create .run/ directory**

```bash
mkdir -p .run
echo "*" > .run/.gitignore     # ignore everything except .gitignore itself
echo "!.gitignore" >> .run/.gitignore
```

This keeps `.run/` tracked but content always ignored.

- [ ] **Step 4: Verify uv sync still works**

```bash
uv sync
```

Expected: 0 errors. Note current tkcp-crawl is at root `tkcp-crawl/` (not yet moved), so `members = ["crawl/txcp"]` is a *future* declaration. uv may warn that the path doesn't exist yet — if so, temporarily set `members = []` and re-add after Sprint 2.

If uv errors on missing path, change `members` to `[]` for Sprint 1 only:
```toml
[tool.uv.workspace]
members = []
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore .run/.gitignore
git commit -m "$(cat <<'EOF'
chore(workspace): root pyproject + .gitignore + .run/ for sprint-by-sprint repo restructure

Workspace root with empty members initially — each sprint adds its package.
.run/ tracks but ignores content (pid + log files at runtime).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 3: Sprint-1 verification gate

- [ ] **Step 1: Existing tkcp-crawl still works**

```bash
cd tkcp-crawl
uv run pytest -m "not live" 2>&1 | tail -3
cd ..
```

Expected: 34 passed. **If fail → rollback (`git reset --hard HEAD~1`) and diagnose.**

---

## Sprint 2 — Move tkcp-crawl → crawl/txcp/

**Goal:** Rename + relocate. Package `tkcp_crawl` → `txcp_crawl`. Tests pass after each step.

### Task 4: git mv tkcp-crawl → crawl/txcp/

**Files:**
- Move: `tkcp-crawl/` → `crawl/txcp/`

- [ ] **Step 1: Create crawl/ parent + git mv**

```bash
mkdir -p crawl
git mv tkcp-crawl crawl/txcp
git status --short
```

Expected: `R tkcp-crawl/... -> crawl/txcp/...` for each file.

- [ ] **Step 2: Verify imports still resolve from new path**

```bash
cd crawl/txcp
uv run python -c "from tkcp_crawl import CampRecord, pull; print('OK')"
cd ../..
```

Expected: `OK`. (Package name still `tkcp_crawl` at this step — only directory moved.)

- [ ] **Step 3: Run tests from new location**

```bash
cd crawl/txcp
uv run pytest -m "not live" 2>&1 | tail -3
cd ../..
```

Expected: 34 passed.

- [ ] **Step 4: Commit (move only)**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: move tkcp-crawl → crawl/txcp/ (directory only; package rename next)

git mv preserves history for all 24 files.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 5: Rename package tkcp_crawl → txcp_crawl

**Files:**
- Move: `crawl/txcp/src/tkcp_crawl/` → `crawl/txcp/src/txcp_crawl/`
- Modify: `crawl/txcp/pyproject.toml` (name + scripts entry + wheel package)
- Modify: `crawl/txcp/src/txcp_crawl/__init__.py`, `cli.py`, `crawler.py`, `adapter.py`, `fetcher.py`, `models.py`, `csv_writer.py`, `state.py`, `stealth.py`, `settings.py` (any internal import of `tkcp_crawl` → `txcp_crawl`)
- Modify: `crawl/txcp/tests/*.py` (every `from tkcp_crawl` → `from txcp_crawl`)
- Modify: `crawl/txcp/README.md` (any `tkcp_crawl`/`tkcp-crawl` references — check carefully, "tkcp-crawl" the OLD name should become "txcp-crawl" the NEW name; references to the SITE "thankqcamping" and category codes BB000-BB006 stay unchanged)

- [ ] **Step 1: git mv the package directory**

```bash
git mv crawl/txcp/src/tkcp_crawl crawl/txcp/src/txcp_crawl
```

- [ ] **Step 2: Rewrite imports — find all occurrences first**

```bash
grep -rln "tkcp_crawl" crawl/txcp/ 2>&1
```

Expected: list of files containing `tkcp_crawl` token (production + tests).

- [ ] **Step 3: Apply sed rewrite (Python imports)**

For each .py file found above (run in WSL bash):
```bash
find crawl/txcp -name "*.py" -type f -exec sed -i 's/tkcp_crawl/txcp_crawl/g' {} +
```

Verify:
```bash
grep -rn "tkcp_crawl" crawl/txcp/ --include="*.py" 2>&1 || echo "all rewritten"
```

Expected: `all rewritten` (no matches).

- [ ] **Step 4: Update crawl/txcp/pyproject.toml (3 places)**

Edit `crawl/txcp/pyproject.toml`:
- `[project] name = "tkcp-crawl"` → `name = "txcp-crawl"`
- `[project.scripts] tkcp-crawl = "tkcp_crawl.cli:app"` → `txcp-crawl = "txcp_crawl.cli:app"`
- `[tool.hatch.build.targets.wheel] packages = ["src/tkcp_crawl"]` → `packages = ["src/txcp_crawl"]`

- [ ] **Step 5: Update README.md references**

In `crawl/txcp/README.md`:
- All `tkcp-crawl` (the package/CLI name) → `txcp-crawl`
- All `tkcp_crawl` (the import path) → `txcp_crawl`
- Heading `# tkcp-crawl` → `# txcp-crawl`

Keep unchanged: "thankqcamping", site URLs, BB000-BB006 codes, "tkcp" prefix in `_source` value (was "thankqcamping" anyway — not a tkcp/txcp string).

Use sed for fenced/code commands:
```bash
sed -i 's/tkcp-crawl/txcp-crawl/g; s/tkcp_crawl/txcp_crawl/g' crawl/txcp/README.md
grep -E "tkcp" crawl/txcp/README.md || echo "clean"
```

Expected: `clean`.

- [ ] **Step 6: Update `_source` value if needed**

Check production code for hardcoded "thankqcamping" — should remain (it's the data source identifier, NOT the package name). Verify no "tkcp" string leaked anywhere unintended:
```bash
grep -rn "tkcp" crawl/txcp/ --include="*.py" 2>&1
grep -rn "tkcp" crawl/txcp/README.md 2>&1
```

Expected: no matches.

- [ ] **Step 7: Update root pyproject.toml workspace member name (if changed)**

The members path is `"crawl/txcp"` (directory name) — not affected by package rename. No change needed.

- [ ] **Step 8: uv sync from root**

```bash
cd /mnt/d/github/cf
uv sync
```

Expected: 0 errors. txcp-crawl resolved.

- [ ] **Step 9: Test from root (workspace mode)**

```bash
cd /mnt/d/github/cf
uv run --package txcp-crawl pytest crawl/txcp -m "not live" 2>&1 | tail -3
```

Expected: 34 passed.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: rename tkcp_crawl → txcp_crawl package (crawl/txcp/)

- src/tkcp_crawl/ → src/txcp_crawl/ (git mv)
- All Python imports rewritten via sed
- pyproject.toml: name, console script, wheel package paths updated
- README.md: package/CLI references updated
- _source data identifier "thankqcamping" stays unchanged (not a package name)

Tests: 34/34 PASS via uv run --package txcp-crawl

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 6: Sprint-2 verification gate

- [ ] **Step 1: Full test from workspace root**

```bash
cd /mnt/d/github/cf
uv run --package txcp-crawl pytest crawl/txcp -m "not live" -v 2>&1 | tail -10
```

Expected: 34 passed. **If fail → `git reset --hard HEAD~2` and diagnose. Don't proceed to S3.**

- [ ] **Step 2: Check tkcp-crawl/ no longer exists**

```bash
test -d /mnt/d/github/cf/tkcp-crawl && echo "STILL EXISTS — FIX" || echo "moved OK"
```

Expected: `moved OK`.

---

## Sprint 3 — Move camfit-puller crawler core → crawl/camfit/

**Goal:** Extract crawler-only modules + scripts + tests from camfit-puller. Rename package `camfit_puller` (crawl subset) → `camfit_crawl`. Backend + pipeline parts remain in camfit-puller for now.

### Task 7: Create crawl/camfit/ scaffold

**Files:**
- Create: `crawl/camfit/pyproject.toml`
- Create: `crawl/camfit/README.md`
- Create: `crawl/camfit/src/camfit_crawl/__init__.py`
- Create: `crawl/camfit/tests/__init__.py`
- Create: `crawl/camfit/scripts/` (empty dir tracker)
- Create: `crawl/camfit/.gitignore`

- [ ] **Step 1: Create crawl/camfit/pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "camfit-crawl"
version = "0.1.0"
description = "Polite camfit.co.kr camping list crawler — sibling of txcp-crawl."
requires-python = ">=3.11"
authors = [{ name = "cxx_2" }]
license = { text = "MIT" }
readme = "README.md"

dependencies = [
    "httpx>=0.27",
    "selectolax>=0.3.21",
    "lxml>=5.2",
    "typer>=0.12",
    "pydantic>=2.7",
    "pydantic-settings>=2.4",
    "loguru>=0.7",
    "tenacity>=8.2",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "pytest-asyncio>=0.23", "respx>=0.21"]
playwright = ["playwright>=1.44"]

[project.scripts]
camfit-crawl = "camfit_crawl.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/camfit_crawl"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "integration: integration tests requiring docker stack",
    "live: requires live network",
]
```

- [ ] **Step 2: Create crawl/camfit/README.md**

```markdown
# camfit-crawl

Polite camfit.co.kr camping list crawler. Sibling of `crawl/txcp/` (thankqcamping).

## Install

```sh
uv sync   # from repo root (workspace)
```

## Usage

```sh
uv run --package camfit-crawl python -m camfit_crawl.cli pull --help
```

Output: `data/` (jsonl + csv, gitignored).

## Migrated from camfit-puller

Was `camfit-puller/src/camfit_puller/` — crawler-only modules. Backend (FastAPI + clean-arch) lives in `backend/`. Post-crawl pipeline lives in `pipeline/`.
```

- [ ] **Step 3: Create crawl/camfit/.gitignore**

```
__pycache__/
*.pyc
.pytest_cache/
data/
.venv/
```

- [ ] **Step 4: Create crawl/camfit/src/camfit_crawl/__init__.py + tests/__init__.py**

`crawl/camfit/src/camfit_crawl/__init__.py`:
```python
"""camfit-crawl — camfit.co.kr crawler.

Migrated from camfit-puller (crawl-only subset).
"""
__version__ = "0.1.0"
```

`crawl/camfit/tests/__init__.py`: empty file.

- [ ] **Step 5: Add to root workspace members**

Edit `pyproject.toml` (root):
```toml
[tool.uv.workspace]
members = ["crawl/txcp", "crawl/camfit"]
```

- [ ] **Step 6: uv sync verifies**

```bash
cd /mnt/d/github/cf
uv sync
```

Expected: 0 errors. camfit-crawl recognized.

- [ ] **Step 7: Commit scaffold**

```bash
git add crawl/camfit/ pyproject.toml
git commit -m "feat(crawl/camfit): scaffold package — pyproject + README + workspace member"
```

### Task 8: Move crawler module files

**Files:**
- Move (git mv) these from `camfit-puller/src/camfit_puller/` to `crawl/camfit/src/camfit_crawl/`:
  - `crawler.py`, `parser.py`, `models.py`, `stealth.py`, `csv_writer.py`, `etago_adapter.py`, `cli.py`, `settings.py`

- [ ] **Step 1: git mv each file** (8 files)

```bash
cd /mnt/d/github/cf
for f in crawler.py parser.py models.py stealth.py csv_writer.py etago_adapter.py cli.py settings.py; do
    git mv camfit-puller/src/camfit_puller/$f crawl/camfit/src/camfit_crawl/$f
done
git status --short | head -10
```

Expected: 8 R (rename) entries.

- [ ] **Step 2: Verify relative imports still work**

`grep` to confirm internal modules use relative imports:
```bash
grep -rn "from camfit_puller\|import camfit_puller" crawl/camfit/src/camfit_crawl/ 2>&1
```

Expected: NO matches (src/ uses relative imports per pre-flight investigation).

- [ ] **Step 3: Find any absolute imports that DO need rewrite**

Some modules might reference camfit_puller submodules that didn't move (e.g., domain/, ports/). Check:
```bash
grep -rn "camfit_puller\." crawl/camfit/src/camfit_crawl/ 2>&1
```

If matches found, those modules import from backend portions still in camfit-puller. Document each:

For Sprint 3 we expect crawler core to NOT depend on backend (domain/ports/usecases/adapters). If it does, that's a design issue — flag in step 4.

- [ ] **Step 4: Rewrite any cross-package imports**

If grep found `from camfit_puller.domain.X import Y` etc., we have two options:
- (a) Sprint 3 deferred: leave those imports broken until Sprint 5 (backend) lands. Mark TODO.
- (b) Sprint 3 immediate: copy minimal needed types into crawl/camfit/src/camfit_crawl/_compat.py. Document in handoff.

If no matches, proceed.

For each match `from camfit_puller.X import Y`:
- If X is `domain`/`ports`/`usecases`/`adapters` (backend) → mark TODO; skip this sprint, address in Sprint 5.
- If X is some other crawler internal → it's a relative-able import; rewrite to `from .X import Y` if X is now in `camfit_crawl/`.

- [ ] **Step 5: Try to import the package**

```bash
cd /mnt/d/github/cf
uv run --package camfit-crawl python -c "from camfit_crawl import models, parser, stealth, csv_writer, crawler, cli, settings, etago_adapter; print('imports OK')"
```

Expected: `imports OK`. If ImportError, fix per step 4.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: move camfit crawler modules to crawl/camfit/src/camfit_crawl/

8 modules: crawler / parser / models / stealth / csv_writer / etago_adapter / cli / settings.
src/ uses relative imports — no rewrite needed inside moved modules.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 9: Move crawler scripts

**Files:**
- Move from `camfit-puller/scripts/`: `cf_pull_*.py`, `cf_dedup_to_csv.py`, `cf_grab.py`, `cf_inspect_*.py`, `fetch_cf_home_scrapling.py`, `_state_audit.py`, `summarize_camfit_snapshot.py` → `crawl/camfit/scripts/`

- [ ] **Step 1: List crawler scripts (the ones that move)**

The crawler scripts are:
- cf_pull_browser_targeted.py
- cf_pull_collections.py
- cf_pull_details.py
- cf_pull_expanded.py
- cf_pull_remaining.py
- cf_pull_themes.py
- cf_pull_via_scroll.py
- cf_dedup_to_csv.py
- cf_grab.py
- cf_inspect_api.py
- cf_inspect_detail.py
- cf_inspect_filters.py
- cf_inspect_region_filter.py
- cf_search_inspect.py
- fetch_cf_home_scrapling.py
- _state_audit.py
- summarize_camfit_snapshot.py

(NOT moving — these go to pipeline/ in Sprint 6: `cf_load_rich.py`, `migrate_to_pg.py`, `derive_lexicon.py`, `seed_concepts.py`, `seed_filter_mapping.py`, `cf_geocode.py`)

- [ ] **Step 2: git mv each crawler script**

```bash
cd /mnt/d/github/cf
mkdir -p crawl/camfit/scripts
for f in cf_pull_browser_targeted.py cf_pull_collections.py cf_pull_details.py cf_pull_expanded.py cf_pull_remaining.py cf_pull_themes.py cf_pull_via_scroll.py cf_dedup_to_csv.py cf_grab.py cf_inspect_api.py cf_inspect_detail.py cf_inspect_filters.py cf_inspect_region_filter.py cf_search_inspect.py fetch_cf_home_scrapling.py _state_audit.py summarize_camfit_snapshot.py; do
    if [ -f "camfit-puller/scripts/$f" ]; then
        git mv "camfit-puller/scripts/$f" "crawl/camfit/scripts/$f"
    fi
done
git status --short | head -20
```

- [ ] **Step 3: Rewrite imports in moved scripts**

Many scripts have `from camfit_puller.X import Y`. Rewrite:

```bash
find crawl/camfit/scripts -name "*.py" -type f -exec sed -i 's/from camfit_puller\./from camfit_crawl./g; s/import camfit_puller$/import camfit_crawl as camfit_puller/g; s/import camfit_puller\./import camfit_crawl./g' {} +
```

Verify:
```bash
grep -rn "camfit_puller" crawl/camfit/scripts/ 2>&1 || echo "all rewritten"
```

If any match remains (e.g., a script imports `camfit_puller.container` which is BACKEND), that script depends on backend. Either:
- Defer the script to Sprint 6 (pipeline/) since it's actually a pipeline script
- Or mark the script with a "broken until Sprint 5" TODO comment at top

For each remaining match, decide — most likely they're pipeline scripts already excluded in Step 1.

- [ ] **Step 4: Quick syntax check (no execution)**

```bash
uv run --package camfit-crawl python -m py_compile crawl/camfit/scripts/cf_pull_via_scroll.py crawl/camfit/scripts/cf_grab.py crawl/camfit/scripts/cf_inspect_api.py 2>&1 || echo "compile errors"
```

Expected: no output (clean). If errors, fix imports in offending file.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: move crawler scripts to crawl/camfit/scripts/

17 scripts (cf_pull_*, cf_dedup_to_csv, cf_grab, cf_inspect_*, fetch_*, _state_audit, summarize_*).
Imports rewritten: from camfit_puller → from camfit_crawl.
Pipeline scripts (cf_load_rich, migrate_to_pg, derive_lexicon, seed_*, cf_geocode) defer to Sprint 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 10: Move crawler tests

**Files:**
- Move from `camfit-puller/tests/`: `test_crawler_respx.py`, `test_csv_writer.py`, `test_parser.py`, `test_stealth.py`, `test_etago_adapter.py`, `smoke_etago_geo.py` → `crawl/camfit/tests/`

- [ ] **Step 1: git mv 6 test files**

```bash
cd /mnt/d/github/cf
for f in test_crawler_respx.py test_csv_writer.py test_parser.py test_stealth.py test_etago_adapter.py smoke_etago_geo.py; do
    git mv "camfit-puller/tests/$f" "crawl/camfit/tests/$f"
done
git status --short | head -10
```

- [ ] **Step 2: Rewrite test imports**

```bash
find crawl/camfit/tests -name "*.py" -type f -exec sed -i 's/from camfit_puller\./from camfit_crawl./g; s/import camfit_puller$/import camfit_crawl as camfit_puller/g; s/import camfit_puller\./import camfit_crawl./g' {} +
```

Verify:
```bash
grep -rn "camfit_puller" crawl/camfit/tests/ 2>&1 || echo "all rewritten"
```

- [ ] **Step 3: Run tests from new location**

```bash
cd /mnt/d/github/cf
uv run --package camfit-crawl pytest crawl/camfit/tests -m "not live and not integration" -v 2>&1 | tail -20
```

Expected: All tests collected and PASS. If failures, root-cause:
- ImportError → check rewrite for that file.
- Fixture missing → check if fixture comes from a tests/ subdir that didn't move.
- Behavior fail → original test broken in current code.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
test(crawl/camfit): move 6 crawler tests + rewrite imports

test_crawler_respx / test_csv_writer / test_parser / test_stealth /
test_etago_adapter / smoke_etago_geo. All from camfit_puller → from camfit_crawl.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 11: Sprint-3 verification gate

- [ ] **Step 1: Full pytest pass for both crawl packages**

```bash
cd /mnt/d/github/cf
uv run --package txcp-crawl pytest crawl/txcp -m "not live" 2>&1 | tail -3
uv run --package camfit-crawl pytest crawl/camfit -m "not live and not integration" 2>&1 | tail -3
```

Expected: both PASS. **If any fail → `git reset --hard HEAD~3` rollback to Sprint-2 end and diagnose.**

- [ ] **Step 2: camfit-puller/ still importable (haven't removed yet)**

```bash
cd /mnt/d/github/cf/camfit-puller
uv run python -c "from camfit_puller import api" 2>&1 | tail -3 || echo "expected: api still works (backend not yet moved)"
cd ..
```

Expected: `api` imports OK (we only moved crawler files; backend still intact).

---

## Sprint 4 — Move camfit data dir → crawl/camfit/data/

**Goal:** Relocate accumulated crawl outputs. Single git mv. Verify content integrity.

### Task 12: Move data directory

**Files:**
- Move: `camfit-puller/data/` → `crawl/camfit/data/`

- [ ] **Step 1: Inspect what's in data/**

```bash
ls /mnt/d/github/cf/camfit-puller/data/ | wc -l
du -sh /mnt/d/github/cf/camfit-puller/data/
```

Note count + size for verification later.

- [ ] **Step 2: Check tracked vs untracked**

```bash
cd /mnt/d/github/cf
git ls-files camfit-puller/data/ | head -5
git status camfit-puller/data/ 2>&1 | head -10
```

If tracked files exist → use git mv. If all untracked → simple `mv` (and rely on the new `crawl/camfit/.gitignore` containing `data/`).

- [ ] **Step 3: Move appropriately**

If untracked:
```bash
mkdir -p crawl/camfit/data
mv camfit-puller/data/* crawl/camfit/data/ 2>/dev/null || true
mv camfit-puller/data/.* crawl/camfit/data/ 2>/dev/null || true
rmdir camfit-puller/data
```

If tracked:
```bash
git mv camfit-puller/data crawl/camfit/data
```

- [ ] **Step 4: Verify content integrity**

```bash
ls crawl/camfit/data/ | wc -l   # should match Step 1 count
du -sh crawl/camfit/data/        # should match Step 1 size
```

- [ ] **Step 5: Verify .gitignore covers it**

```bash
cd /mnt/d/github/cf
git check-ignore crawl/camfit/data/api_001.json 2>&1
```

Expected: prints the file path (meaning ignored). If empty, gitignore not catching → fix `crawl/camfit/.gitignore` to include `data/` (it should already).

- [ ] **Step 6: Commit**

If files were tracked:
```bash
git add -A
git commit -m "chore(crawl/camfit): move data/ from camfit-puller (history preserved)"
```

If files were all untracked, no commit needed for data move itself. Verify state:
```bash
git status --short | head -5
```

### Task 13: Sprint-4 verification gate

- [ ] **Step 1: tests still pass**

```bash
cd /mnt/d/github/cf
uv run --package camfit-crawl pytest crawl/camfit -m "not live and not integration" 2>&1 | tail -3
```

Expected: PASS.

- [ ] **Step 2: data/ exists at new location**

```bash
test -d crawl/camfit/data && echo "OK" || echo "MISSING"
test -d camfit-puller/data && echo "STILL EXISTS — FIX" || echo "moved cleanly"
```

Expected: `OK` then `moved cleanly`.

---

## Sprint 5 — Move backend → backend/

**Goal:** FastAPI + clean-arch from `camfit-puller/src/camfit_puller/{api,container,domain,ports,usecases,adapters}.*` → `backend/src/cf_backend/`.

### Task 14: Create backend/ scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/README.md`
- Create: `backend/src/cf_backend/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/.gitignore`

- [ ] **Step 1: Write backend/pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cf-backend"
version = "0.1.0"
description = "cf backend — FastAPI + DI + clean-arch (domain / ports / usecases / adapters) + DB stack."
requires-python = ">=3.11"
authors = [{ name = "cxx_2" }]
license = { text = "MIT" }
readme = "README.md"

dependencies = [
    "httpx>=0.27",
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

[project.optional-dependencies]
dev = ["pytest>=8.2", "pytest-asyncio>=0.23", "respx>=0.21"]
testcontainers = ["testcontainers[postgres]>=4.7"]

[tool.hatch.build.targets.wheel]
packages = ["src/cf_backend"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "integration: marks tests as integration tests that require a live docker stack",
]
```

- [ ] **Step 2: Write backend/README.md**

```markdown
# cf-backend

FastAPI + clean-arch backend. Migrated from `camfit-puller/src/camfit_puller/{api,container,domain,ports,usecases,adapters}`.

## Layers
- `domain/` — entities, errors, value objects (no IO).
- `ports/` — abstract interfaces (Repo, Graph, Source, Embed, etc.).
- `usecases/` — application services orchestrating ports.
- `adapters/` — concrete impls (falkor, postgres, pgvector, etago_bin, ...).
- `api.py` — FastAPI surface.
- `container.py` — DI wiring.

## Run

```sh
uv run --package cf-backend uvicorn cf_backend.api:app --reload
```

## DB
- falkordb 6379 + postgres 5432 via `docker/docker-compose.yml`. Use `scripts/db-up.sh`.
```

- [ ] **Step 3: backend/.gitignore**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

- [ ] **Step 4: backend/src/cf_backend/__init__.py + tests/__init__.py**

`backend/src/cf_backend/__init__.py`:
```python
"""cf-backend — FastAPI + clean-arch (migrated from camfit_puller)."""
__version__ = "0.1.0"
```

`backend/tests/__init__.py`: empty.

- [ ] **Step 5: Add to root workspace**

Edit `pyproject.toml` (root):
```toml
[tool.uv.workspace]
members = ["crawl/txcp", "crawl/camfit", "backend"]

[tool.uv.sources]
cf-backend = { workspace = true }
```

- [ ] **Step 6: uv sync**

```bash
cd /mnt/d/github/cf
uv sync
```

Expected: 0 errors. cf-backend visible.

- [ ] **Step 7: Commit scaffold**

```bash
git add backend/ pyproject.toml
git commit -m "feat(backend): scaffold cf-backend package — pyproject + README + workspace member"
```

### Task 15: Move backend modules

**Files:**
- Move: `camfit-puller/src/camfit_puller/{api.py,container.py}` → `backend/src/cf_backend/`
- Move: `camfit-puller/src/camfit_puller/{domain,ports,usecases,adapters}/` → `backend/src/cf_backend/`

Note: `settings.py` ALREADY moved to crawl/camfit/ in Sprint 3. Backend will need its own settings (see Step 4).

- [ ] **Step 1: git mv api.py + container.py**

```bash
cd /mnt/d/github/cf
git mv camfit-puller/src/camfit_puller/api.py backend/src/cf_backend/api.py
git mv camfit-puller/src/camfit_puller/container.py backend/src/cf_backend/container.py
```

- [ ] **Step 2: git mv 4 layer directories**

```bash
git mv camfit-puller/src/camfit_puller/domain backend/src/cf_backend/domain
git mv camfit-puller/src/camfit_puller/ports backend/src/cf_backend/ports
git mv camfit-puller/src/camfit_puller/usecases backend/src/cf_backend/usecases
git mv camfit-puller/src/camfit_puller/adapters backend/src/cf_backend/adapters
git status --short | head -20
```

- [ ] **Step 3: Rewrite imports inside moved code**

Many internal references like `from camfit_puller.domain.X import Y`. Rewrite:

```bash
find backend/src/cf_backend -name "*.py" -type f -exec sed -i 's/from camfit_puller\./from cf_backend./g; s/import camfit_puller$/import cf_backend as camfit_puller/g; s/import camfit_puller\./import cf_backend./g' {} +
```

Verify:
```bash
grep -rn "camfit_puller" backend/src/cf_backend/ 2>&1 || echo "all rewritten"
```

- [ ] **Step 4: Create cf_backend/settings.py**

settings.py was moved to crawl/camfit/ but backend code still references `from camfit_puller.settings import Settings`. We need a backend-specific settings.

Inspect what backend code references:
```bash
grep -rn "from cf_backend.settings\|from .settings" backend/src/cf_backend/ 2>&1 | head -10
```

Likely the backend imports Settings via `from .settings`. Since settings.py is now in crawl/camfit/, *copy* a backend-tailored version to backend/src/cf_backend/settings.py.

```bash
# Inspect crawl/camfit version
cat crawl/camfit/src/camfit_crawl/settings.py
```

Create `backend/src/cf_backend/settings.py` containing a Settings class that holds the backend-specific config (DB urls, falkor host, embedding model, etc.). Concrete content depends on what api/container/domain reference — likely `database_url`, `falkordb_host`, etc.

If after grep, the backend modules import Settings from a relative path (`from .settings`), we MUST create the file. Reuse content from camfit-puller's original settings.py.

Strategy:
1. `cp crawl/camfit/src/camfit_crawl/settings.py backend/src/cf_backend/settings.py` (use cp, not mv — crawl needs its own)
2. Edit each side to keep only their relevant fields:
   - crawl: data_dir, delay, base_url, log_level, max_pages
   - backend: database_url, falkordb_host, embedding_model, etc.

Simpler interim: if backend's settings overlap is small, copy entire file as-is, prune later.

```bash
cp crawl/camfit/src/camfit_crawl/settings.py backend/src/cf_backend/settings.py
git add backend/src/cf_backend/settings.py
```

- [ ] **Step 5: Try import**

```bash
cd /mnt/d/github/cf
uv run --package cf-backend python -c "from cf_backend import api; print('api OK')"
```

If ImportError on missing relative submodule (e.g., `domain.X` referenced something now missing), inspect + fix.

If ImportError on missing dep (e.g., a clean-arch port references `from camfit_crawl.models`) — that's a cross-package boundary. Backend should NOT depend on crawl/. Fix by:
- Copy needed model class to `backend/src/cf_backend/domain/` as a backend-internal mirror.
- Or define a smaller protocol in backend/ports/ that the crawl-side can satisfy.

Document each fix.

- [ ] **Step 6: Commit module move**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor(backend): move api / container / domain / ports / usecases / adapters → backend/src/cf_backend/

git mv preserves history. Imports rewritten: camfit_puller.X → cf_backend.X.
settings.py: copied from crawl/camfit (interim — prune later per side).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 16: Move backend tests

**Files:**
- Move: `camfit-puller/tests/{contract,integration,unit,test_graph_api.py,__init__.py}` → `backend/tests/`

- [ ] **Step 1: git mv test directories + files**

```bash
cd /mnt/d/github/cf
git mv camfit-puller/tests/contract backend/tests/contract
git mv camfit-puller/tests/integration backend/tests/integration
git mv camfit-puller/tests/unit backend/tests/unit
git mv camfit-puller/tests/test_graph_api.py backend/tests/test_graph_api.py
# __init__.py — backend/tests/__init__.py already created in Task 14 step 4. Don't overwrite.
git status --short | head -15
```

- [ ] **Step 2: Rewrite imports**

```bash
find backend/tests -name "*.py" -type f -exec sed -i 's/from camfit_puller\./from cf_backend./g; s/import camfit_puller$/import cf_backend as camfit_puller/g; s/import camfit_puller\./import cf_backend./g' {} +
grep -rn "camfit_puller" backend/tests/ 2>&1 || echo "all rewritten"
```

- [ ] **Step 3: Run backend tests**

```bash
cd /mnt/d/github/cf
uv run --package cf-backend pytest backend/tests -m "not integration and not live" -v 2>&1 | tail -20
```

Expected: most pass. Some unit tests may need fixture path updates. If any FAIL, classify:
- ImportError → fix the rewrite for that file.
- Fixture missing → check `conftest.py` location.
- Behavior diff → original test issue (mark in handoff).

- [ ] **Step 4: Commit tests move**

```bash
git add -A
git commit -m "$(cat <<'EOF'
test(backend): move contract/integration/unit + test_graph_api → backend/tests/

Imports rewritten cf_backend.* throughout.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 17: Sprint-5 verification gate

- [ ] **Step 1: All 3 packages tests pass**

```bash
cd /mnt/d/github/cf
uv run --package txcp-crawl pytest crawl/txcp -m "not live" 2>&1 | tail -3
uv run --package camfit-crawl pytest crawl/camfit -m "not live and not integration" 2>&1 | tail -3
uv run --package cf-backend pytest backend -m "not integration and not live" 2>&1 | tail -3
```

Expected: all 3 PASS. **Otherwise rollback Sprint 5 commits and re-do.**

- [ ] **Step 2: backend imports clean**

```bash
uv run --package cf-backend python -c "from cf_backend import api, container; print('OK')"
```

Expected: `OK`.

---

## Sprint 6 — Build pipeline/ from camfit-puller pipeline scripts

**Goal:** Port post-crawl pipeline scripts to `pipeline/src/cf_pipeline/`. Provide `full_run.py` orchestrator.

### Task 18: Create pipeline/ scaffold

**Files:**
- Create: `pipeline/pyproject.toml`
- Create: `pipeline/README.md`
- Create: `pipeline/src/cf_pipeline/__init__.py`
- Create: `pipeline/tests/__init__.py`
- Create: `pipeline/.gitignore`

- [ ] **Step 1: Write pipeline/pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cf-pipeline"
version = "0.1.0"
description = "cf post-crawl pipeline — jsonl → postgres → falkor + etago geocode + lexicon/seed."
requires-python = ">=3.11"
authors = [{ name = "cxx_2" }]
license = { text = "MIT" }
readme = "README.md"

dependencies = [
    "cf-backend",
    "typer>=0.12",
    "loguru>=0.7",
    "pydantic>=2.7",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "pytest-asyncio>=0.23"]

[project.scripts]
cf-pipeline = "cf_pipeline.full_run:app"

[tool.hatch.build.targets.wheel]
packages = ["src/cf_pipeline"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: pipeline/README.md**

```markdown
# cf-pipeline

Post-crawl orchestration:
1. `ingest_camps` — `crawl/{camfit,txcp}/data/camps.jsonl` → postgres `camps` (upsert by source,id).
2. `geocode_run` — null lat/lon → etago binary → UPDATE.
3. `rebuild_graph` — postgres → falkor.
4. `derive_lexicon` — keyword/synonym dict.
5. `seed_concepts`/`seed_filter_mapping` — themes + filter mapping.

## Run

```sh
uv run --package cf-pipeline python -m cf_pipeline.full_run --camfit-data crawl/camfit/data --txcp-data crawl/txcp/data
```

Or via `scripts/migrate.sh` (Sprint 7).
```

- [ ] **Step 3: pipeline/.gitignore**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

- [ ] **Step 4: pipeline/src/cf_pipeline/__init__.py + tests/__init__.py**

`pipeline/src/cf_pipeline/__init__.py`:
```python
"""cf-pipeline — post-crawl jsonl → DB orchestration."""
__version__ = "0.1.0"
```

`pipeline/tests/__init__.py`: empty.

- [ ] **Step 5: Add to root workspace**

Edit `pyproject.toml` (root):
```toml
[tool.uv.workspace]
members = ["crawl/txcp", "crawl/camfit", "backend", "pipeline"]

[tool.uv.sources]
cf-backend = { workspace = true }
```

- [ ] **Step 6: uv sync**

```bash
uv sync
```

Expected: 0 errors. cf-pipeline + cf-backend dep resolved.

- [ ] **Step 7: Commit scaffold**

```bash
git add pipeline/ pyproject.toml
git commit -m "feat(pipeline): scaffold cf-pipeline package — workspace member, dep cf-backend"
```

### Task 19: Port pipeline scripts

**Files:**
- Move: `camfit-puller/scripts/{migrate_to_pg,cf_load_rich,derive_lexicon,seed_concepts,seed_filter_mapping,cf_geocode}.py` → `pipeline/src/cf_pipeline/`

- [ ] **Step 1: git mv 6 scripts (with rename)**

```bash
cd /mnt/d/github/cf
git mv camfit-puller/scripts/migrate_to_pg.py pipeline/src/cf_pipeline/ingest_camps.py
git mv camfit-puller/scripts/cf_load_rich.py pipeline/src/cf_pipeline/load_rich.py
git mv camfit-puller/scripts/derive_lexicon.py pipeline/src/cf_pipeline/derive_lexicon.py
git mv camfit-puller/scripts/seed_concepts.py pipeline/src/cf_pipeline/seed_concepts.py
git mv camfit-puller/scripts/seed_filter_mapping.py pipeline/src/cf_pipeline/seed_filter_mapping.py
git mv camfit-puller/scripts/cf_geocode.py pipeline/src/cf_pipeline/geocode_run.py
```

- [ ] **Step 2: Rewrite imports**

```bash
find pipeline/src/cf_pipeline -name "*.py" -type f -exec sed -i 's/from camfit_puller\./from cf_backend./g; s/import camfit_puller$/import cf_backend as camfit_puller/g; s/import camfit_puller\./import cf_backend./g' {} +
grep -rn "camfit_puller" pipeline/src/cf_pipeline/ 2>&1 || echo "all rewritten"
```

- [ ] **Step 3: Verify each script imports**

```bash
uv run --package cf-pipeline python -c "from cf_pipeline import ingest_camps, load_rich, derive_lexicon, seed_concepts, seed_filter_mapping, geocode_run; print('OK')"
```

Expected: `OK`. Fix any ImportError.

- [ ] **Step 4: Commit scripts port**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor(pipeline): port 6 post-crawl scripts to cf_pipeline package

Renames: migrate_to_pg → ingest_camps, cf_geocode → geocode_run.
Imports rewritten camfit_puller → cf_backend.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 20: Build full_run.py orchestrator

**Files:**
- Create: `pipeline/src/cf_pipeline/full_run.py`
- Test: `pipeline/tests/test_full_run_dry.py`

- [ ] **Step 1: Write failing test FIRST (TDD)**

`pipeline/tests/test_full_run_dry.py`:
```python
"""full_run --dry-run: must print plan + exit 0 without DB calls."""
from __future__ import annotations
import subprocess
import sys


def test_dry_run_exits_zero_with_plan_output():
    result = subprocess.run(
        [sys.executable, "-m", "cf_pipeline.full_run", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = result.stdout + result.stderr
    # All 5 stages must be listed
    assert "ingest_camps" in out
    assert "geocode_run" in out
    assert "rebuild_graph" in out
    assert "derive_lexicon" in out
    assert "seed" in out


def test_only_flag_runs_subset():
    result = subprocess.run(
        [sys.executable, "-m", "cf_pipeline.full_run", "--dry-run", "--only", "ingest_camps"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert "ingest_camps" in out
    # Other stages should be skipped indication
    assert "skip" in out.lower() or "only" in out.lower()
```

- [ ] **Step 2: Run test — confirm failure**

```bash
uv run --package cf-pipeline pytest pipeline/tests/test_full_run_dry.py -v 2>&1 | tail -10
```

Expected: FAIL with "No module named cf_pipeline.full_run" or similar.

- [ ] **Step 3: Write full_run.py minimal impl**

`pipeline/src/cf_pipeline/full_run.py`:
```python
"""full_run — orchestrate 5 pipeline stages.

Stage order (each idempotent):
  1. ingest_camps    : crawl/{camfit,txcp}/data/camps.jsonl → postgres camps upsert
  2. geocode_run     : null lat/lon rows → etago binary → UPDATE
  3. rebuild_graph   : postgres → falkor
  4. derive_lexicon  : keyword/synonym dict refresh
  5. seed_concepts + seed_filter_mapping : theme + filter mapping
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

app = typer.Typer(no_args_is_help=False, add_completion=False)

STAGES = [
    "ingest_camps",
    "geocode_run",
    "rebuild_graph",
    "derive_lexicon",
    "seed_concepts",
    "seed_filter_mapping",
]


@app.command()
def main(
    camfit_data: Path = typer.Option(Path("crawl/camfit/data"), help="camfit data dir"),
    txcp_data: Path = typer.Option(Path("crawl/txcp/data"), help="txcp data dir"),
    only: Optional[str] = typer.Option(None, help="run only this stage"),
    skip: list[str] = typer.Option([], help="skip these stages"),
    dry_run: bool = typer.Option(False, help="print plan without executing"),
) -> None:
    selected = [s for s in STAGES if (only is None or s == only) and s not in skip]
    if not selected:
        typer.echo("No stages selected. Available: " + ", ".join(STAGES), err=True)
        raise typer.Exit(code=1)

    typer.echo(f"=== cf-pipeline full_run plan ===")
    typer.echo(f"camfit_data = {camfit_data}")
    typer.echo(f"txcp_data   = {txcp_data}")
    typer.echo(f"dry_run     = {dry_run}")
    typer.echo(f"stages      = {selected}")
    if only is None and skip:
        typer.echo(f"skipped     = {skip}")

    for stage in STAGES:
        if stage in selected:
            typer.echo(f"  RUN  {stage}")
        else:
            typer.echo(f"  skip {stage}")

    if dry_run:
        typer.echo("=== DRY RUN — no execution ===")
        raise typer.Exit(code=0)

    # Real execution dispatch — each stage is a function call.
    # Stages may take long; this is the orchestrator only.
    for stage in selected:
        logger.info(f"--- stage: {stage} ---")
        if stage == "ingest_camps":
            from cf_pipeline.ingest_camps import run as ingest_run
            ingest_run(camfit_data=camfit_data, txcp_data=txcp_data)
        elif stage == "geocode_run":
            from cf_pipeline.geocode_run import run as geo_run
            geo_run()
        elif stage == "rebuild_graph":
            from cf_pipeline import load_rich  # noqa: F401  (placeholder — actual rebuild)
            logger.warning("rebuild_graph: placeholder — see pipeline/src/cf_pipeline/load_rich.py")
        elif stage == "derive_lexicon":
            from cf_pipeline import derive_lexicon
            derive_lexicon  # noqa: B018 (run via __main__ block in original script)
            logger.warning("derive_lexicon: invoke as separate __main__ — port pending")
        elif stage == "seed_concepts":
            from cf_pipeline import seed_concepts
            seed_concepts  # noqa
            logger.warning("seed_concepts: invoke as __main__ — port pending")
        elif stage == "seed_filter_mapping":
            from cf_pipeline import seed_filter_mapping
            seed_filter_mapping  # noqa
            logger.warning("seed_filter_mapping: invoke as __main__ — port pending")


if __name__ == "__main__":
    app()
```

Note: original camfit-puller scripts may have `if __name__ == "__main__"` blocks. The orchestrator's job is to dispatch — but full impl of "run as a function" requires refactoring each ported script's `__main__` block into a `def run(...)`. For Sprint 6 scope, the orchestrator + dry-run is sufficient; per-stage `def run` adapters are a follow-up sprint extension.

- [ ] **Step 4: Run test — confirm PASS**

```bash
cd /mnt/d/github/cf
uv run --package cf-pipeline pytest pipeline/tests/test_full_run_dry.py -v 2>&1 | tail -10
```

Expected: 2 passed.

- [ ] **Step 5: Add ingest_camps `def run` adapter**

In `pipeline/src/cf_pipeline/ingest_camps.py` (formerly `migrate_to_pg.py`), wrap the existing main logic into a callable `def run(camfit_data: Path, txcp_data: Path) -> None:`. Inspect the file to identify the `__main__` block, extract its body into `run`.

This is one targeted edit per stage — focus on `ingest_camps` for Sprint 6, others are stretch.

```bash
# Inspect the file to plan the wrap
head -40 pipeline/src/cf_pipeline/ingest_camps.py
```

If `if __name__ == "__main__":` block exists with a body, refactor:
```python
def run(camfit_data: Path, txcp_data: Path) -> None:
    # ... existing __main__ body ...
    pass


if __name__ == "__main__":
    run(camfit_data=Path("crawl/camfit/data"), txcp_data=Path("crawl/txcp/data"))
```

- [ ] **Step 6: Commit full_run + ingest_camps adapter**

```bash
git add pipeline/src/cf_pipeline/full_run.py pipeline/src/cf_pipeline/ingest_camps.py pipeline/tests/test_full_run_dry.py
git commit -m "$(cat <<'EOF'
feat(pipeline): full_run orchestrator + dry-run + ingest_camps adapter

5-stage plan (ingest / geocode / rebuild_graph / derive_lexicon / seed_*).
--dry-run prints plan, exit 0 (no DB).
--only / --skip filter stages.
ingest_camps: def run(camfit_data, txcp_data) — rest of stages stretch.

Tests: 2 PASS (test_full_run_dry).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 21: Sprint-6 verification gate

- [ ] **Step 1: All 4 packages tests pass**

```bash
cd /mnt/d/github/cf
uv run --package txcp-crawl pytest crawl/txcp -m "not live" 2>&1 | tail -3
uv run --package camfit-crawl pytest crawl/camfit -m "not live and not integration" 2>&1 | tail -3
uv run --package cf-backend pytest backend -m "not integration and not live" 2>&1 | tail -3
uv run --package cf-pipeline pytest pipeline -m "not live" 2>&1 | tail -3
```

Expected: all PASS. **Otherwise rollback Sprint 6 commits.**

- [ ] **Step 2: full_run dry-run smoke**

```bash
uv run --package cf-pipeline python -m cf_pipeline.full_run --dry-run
```

Expected: 5-stage plan output + `DRY RUN — no execution`.

---

## Sprint 7 — Root scripts/

**Goal:** sh-only ops scripts. tested via simple sh assertions.

### Task 22: Create scripts/ scaffold + lib/

**Files:**
- Create: `scripts/lib/env.sh`
- Create: `scripts/lib/common.sh`

- [ ] **Step 1: Write scripts/lib/env.sh**

```sh
#!/usr/bin/env bash
# scripts/lib/env.sh — shared env. source this from every script.

set -euo pipefail

# Repo root (allow override)
REPO_ROOT="${REPO_ROOT:-$(git -C "$(dirname "${BASH_SOURCE[0]}")/.." rev-parse --show-toplevel 2>/dev/null || cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export REPO_ROOT

# Run dir (pid + log)
export RUN_DIR="$REPO_ROOT/.run"
mkdir -p "$RUN_DIR"

# Data dirs
export CAMFIT_DATA="$REPO_ROOT/crawl/camfit/data"
export TXCP_DATA="$REPO_ROOT/crawl/txcp/data"

# DB defaults (override via real env)
export DATABASE_URL="${DATABASE_URL:-postgresql://camfit:camfit@localhost:5432/camfit}"
export FALKORDB_URL="${FALKORDB_URL:-redis://localhost:6379}"

# Backend
export BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
export BACKEND_PORT="${BACKEND_PORT:-8000}"
export BACKEND_PID_FILE="$RUN_DIR/backend.pid"
export BACKEND_LOG_FILE="$RUN_DIR/backend.log"
```

- [ ] **Step 2: Write scripts/lib/common.sh**

```sh
#!/usr/bin/env bash
# scripts/lib/common.sh — log + pid helpers.

set -euo pipefail

log_info() { echo "[$(date +%H:%M:%S)] [INFO]  $*" >&2; }
log_warn() { echo "[$(date +%H:%M:%S)] [WARN]  $*" >&2; }
log_error() { echo "[$(date +%H:%M:%S)] [ERROR] $*" >&2; }

pid_alive() {
    local pid="$1"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

write_pid() {
    local file="$1"
    local pid="$2"
    echo "$pid" > "$file"
}

read_pid() {
    local file="$1"
    [ -f "$file" ] || return 1
    cat "$file"
}

stop_pid_file() {
    local file="$1"
    local timeout="${2:-10}"
    local pid
    pid=$(read_pid "$file" 2>/dev/null || echo "")
    if [ -z "$pid" ]; then
        log_warn "no pid file: $file"
        return 0
    fi
    if ! pid_alive "$pid"; then
        log_warn "pid $pid not running"
        rm -f "$file"
        return 0
    fi
    log_info "SIGTERM $pid"
    kill -TERM "$pid"
    local i=0
    while [ $i -lt "$timeout" ] && pid_alive "$pid"; do
        sleep 1
        i=$((i + 1))
    done
    if pid_alive "$pid"; then
        log_warn "SIGKILL $pid"
        kill -KILL "$pid"
    fi
    rm -f "$file"
}
```

- [ ] **Step 3: chmod +x both lib files (Windows note: chmod meaningless on NTFS but tracked in git)**

```bash
chmod +x scripts/lib/env.sh scripts/lib/common.sh
```

- [ ] **Step 4: Commit lib**

```bash
git add scripts/lib/
git commit -m "feat(scripts): lib/env.sh + lib/common.sh — shared env + pid helpers"
```

### Task 23: db-up.sh / db-down.sh / db-status.sh

**Files:**
- Create: `scripts/db-up.sh`, `scripts/db-down.sh`, `scripts/db-status.sh`

- [ ] **Step 1: db-up.sh**

```sh
#!/usr/bin/env bash
# Bring up postgres + falkordb via docker compose. Idempotent.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT/docker"
log_info "docker compose up -d"
docker compose up -d

log_info "waiting for healthchecks (≤60s)"
for i in $(seq 1 60); do
    falkor_h=$(docker compose ps --format json | grep falkordb | grep -c '"Health":"healthy"' || echo "0")
    pg_h=$(docker compose ps --format json | grep postgres | grep -c '"Health":"healthy"' || echo "0")
    if [ "$falkor_h" = "1" ] && [ "$pg_h" = "1" ]; then
        log_info "both healthy after ${i}s"
        exit 0
    fi
    sleep 1
done
log_error "timeout waiting for healthchecks"
docker compose ps
exit 1
```

- [ ] **Step 2: db-down.sh**

```sh
#!/usr/bin/env bash
# Stop containers (volumes preserved).
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT/docker"
log_info "docker compose down (volumes preserved)"
docker compose down
```

- [ ] **Step 3: db-status.sh**

```sh
#!/usr/bin/env bash
# Print container status + ping each.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT/docker"
docker compose ps
echo "---"
docker compose exec -T falkordb redis-cli ping || log_warn "falkordb not responding"
docker compose exec -T postgres pg_isready -U camfit -d camfit || log_warn "postgres not ready"
```

- [ ] **Step 4: chmod + commit**

```bash
chmod +x scripts/db-up.sh scripts/db-down.sh scripts/db-status.sh
git add scripts/db-up.sh scripts/db-down.sh scripts/db-status.sh
git commit -m "feat(scripts): db-up / db-down / db-status (docker compose wrappers)"
```

### Task 24: backend-up.sh / backend-down.sh

**Files:**
- Create: `scripts/backend-up.sh`, `scripts/backend-down.sh`

- [ ] **Step 1: backend-up.sh**

```sh
#!/usr/bin/env bash
# Start uvicorn in background. PID → .run/backend.pid. Log → .run/backend.log.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

if [ -f "$BACKEND_PID_FILE" ]; then
    pid=$(cat "$BACKEND_PID_FILE")
    if pid_alive "$pid"; then
        log_warn "backend already running (pid $pid)"
        exit 0
    fi
    log_warn "stale pid file — removing"
    rm -f "$BACKEND_PID_FILE"
fi

log_info "starting uvicorn cf_backend.api:app on $BACKEND_HOST:$BACKEND_PORT"
cd "$REPO_ROOT"
nohup uv run --package cf-backend uvicorn cf_backend.api:app \
    --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
    > "$BACKEND_LOG_FILE" 2>&1 &
write_pid "$BACKEND_PID_FILE" "$!"
log_info "backend pid $! — log: $BACKEND_LOG_FILE"
```

- [ ] **Step 2: backend-down.sh**

```sh
#!/usr/bin/env bash
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

stop_pid_file "$BACKEND_PID_FILE" 10
log_info "backend stopped"
```

- [ ] **Step 3: chmod + commit**

```bash
chmod +x scripts/backend-up.sh scripts/backend-down.sh
git add scripts/backend-up.sh scripts/backend-down.sh
git commit -m "feat(scripts): backend-up / backend-down (uvicorn nohup + pid file)"
```

### Task 25: crawl-camfit.sh / crawl-txcp.sh / migrate.sh

**Files:**
- Create: 3 scripts

- [ ] **Step 1: crawl-camfit.sh**

```sh
#!/usr/bin/env bash
# Pull camfit camping list. Args passthrough.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT"
log_info "camfit-crawl pull (args: $*)"
exec uv run --package camfit-crawl python -m camfit_crawl.cli pull "$@"
```

- [ ] **Step 2: crawl-txcp.sh**

```sh
#!/usr/bin/env bash
# Pull txcp (thankqcamping) camping list. Args passthrough.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT"
log_info "txcp-crawl pull (args: $*)"
exec uv run --package txcp-crawl python -m txcp_crawl.cli pull "$@"
```

- [ ] **Step 3: migrate.sh**

```sh
#!/usr/bin/env bash
# Full pipeline: jsonl → postgres → falkor + etago geocode + lexicon/seed.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT"
log_info "cf-pipeline full_run (args: $*)"
exec uv run --package cf-pipeline python -m cf_pipeline.full_run \
    --camfit-data "$CAMFIT_DATA" \
    --txcp-data "$TXCP_DATA" \
    "$@"
```

- [ ] **Step 4: chmod + commit**

```bash
chmod +x scripts/crawl-camfit.sh scripts/crawl-txcp.sh scripts/migrate.sh
git add scripts/crawl-camfit.sh scripts/crawl-txcp.sh scripts/migrate.sh
git commit -m "feat(scripts): crawl-camfit / crawl-txcp / migrate (uv run wrappers)"
```

### Task 26: setup.sh / teardown.sh / dev-status.sh / test.sh

**Files:**
- Create: `scripts/setup.sh`, `scripts/teardown.sh`, `scripts/dev-status.sh`, `scripts/test.sh`

- [ ] **Step 1: setup.sh**

```sh
#!/usr/bin/env bash
# One-shot dev setup: uv sync + db-up + backend-up.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT"
log_info "uv sync"
uv sync
"$REPO_ROOT/scripts/db-up.sh"
"$REPO_ROOT/scripts/backend-up.sh"
log_info "setup complete"
```

- [ ] **Step 2: teardown.sh**

```sh
#!/usr/bin/env bash
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

"$REPO_ROOT/scripts/backend-down.sh"
"$REPO_ROOT/scripts/db-down.sh"
log_info "teardown complete"
```

- [ ] **Step 3: dev-status.sh**

```sh
#!/usr/bin/env bash
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

echo "=== DB ==="
"$REPO_ROOT/scripts/db-status.sh"
echo "=== Backend ==="
if [ -f "$BACKEND_PID_FILE" ]; then
    pid=$(cat "$BACKEND_PID_FILE")
    if pid_alive "$pid"; then
        echo "backend pid $pid alive (port $BACKEND_PORT)"
    else
        echo "backend pid file stale ($pid not alive)"
    fi
else
    echo "backend not running"
fi
echo "=== Last 10 backend log lines ==="
tail -n 10 "$BACKEND_LOG_FILE" 2>/dev/null || echo "(no log)"
```

- [ ] **Step 4: test.sh**

```sh
#!/usr/bin/env bash
# Run pytest "not live" across all 4 packages.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT"
fail=0
for pkg in txcp-crawl camfit-crawl cf-backend cf-pipeline; do
    log_info "=== $pkg ==="
    case "$pkg" in
        txcp-crawl)    path=crawl/txcp ;;
        camfit-crawl)  path=crawl/camfit ;;
        cf-backend)    path=backend ;;
        cf-pipeline)   path=pipeline ;;
    esac
    if ! uv run --package "$pkg" pytest "$path" -m "not live and not integration" --tb=short 2>&1 | tail -5; then
        fail=1
    fi
done
[ $fail -eq 0 ] && log_info "ALL PASS" || { log_error "SOME FAILED"; exit 1; }
```

- [ ] **Step 5: chmod + commit**

```bash
chmod +x scripts/setup.sh scripts/teardown.sh scripts/dev-status.sh scripts/test.sh
git add scripts/setup.sh scripts/teardown.sh scripts/dev-status.sh scripts/test.sh
git commit -m "feat(scripts): setup / teardown / dev-status / test (workflow shortcuts)"
```

### Task 27: scripts/tests/ — sh assertions

**Files:**
- Create: `scripts/tests/run.sh`
- Create: `scripts/tests/test_db_scripts.sh`
- Create: `scripts/tests/test_backend_pid.sh`
- Create: `scripts/tests/test_migrate_dryrun.sh`

- [ ] **Step 1: scripts/tests/run.sh — runner**

```sh
#!/usr/bin/env bash
. "$(dirname "$0")/../lib/env.sh"
. "$(dirname "$0")/../lib/common.sh"

cd "$(dirname "$0")"
fail=0
for t in test_*.sh; do
    log_info "=== $t ==="
    if ! bash "$t"; then
        log_error "$t FAILED"
        fail=1
    fi
done
[ $fail -eq 0 ] && { log_info "ALL ASSERTIONS PASS"; exit 0; } || exit 1
```

- [ ] **Step 2: test_db_scripts.sh — only check syntax (don't actually start docker)**

```sh
#!/usr/bin/env bash
# Verify db-*.sh files are syntactically valid bash.
set -euo pipefail
. "$(dirname "$0")/../lib/env.sh"

for f in db-up.sh db-down.sh db-status.sh; do
    bash -n "$REPO_ROOT/scripts/$f" || { echo "SYNTAX FAIL: $f"; exit 1; }
done
echo "db-* scripts syntactically valid"
```

- [ ] **Step 3: test_backend_pid.sh — pid helper unit test**

```sh
#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../lib/common.sh"

# write_pid + read_pid
tmp=$(mktemp)
write_pid "$tmp" "12345"
got=$(read_pid "$tmp")
[ "$got" = "12345" ] || { echo "FAIL: write_pid/read_pid roundtrip"; exit 1; }
rm -f "$tmp"

# pid_alive of bogus pid
if pid_alive "999999999"; then
    echo "FAIL: pid_alive returned true for bogus pid"
    exit 1
fi
echo "pid helpers OK"
```

- [ ] **Step 4: test_migrate_dryrun.sh — actual dry-run smoke**

```sh
#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../lib/env.sh"

cd "$REPO_ROOT"
output=$(uv run --package cf-pipeline python -m cf_pipeline.full_run --dry-run 2>&1)
echo "$output" | grep -q "ingest_camps" || { echo "FAIL: ingest_camps missing"; exit 1; }
echo "$output" | grep -q "DRY RUN" || { echo "FAIL: DRY RUN marker missing"; exit 1; }
echo "migrate dry-run OK"
```

- [ ] **Step 5: chmod + run + commit**

```bash
chmod +x scripts/tests/run.sh scripts/tests/test_*.sh
bash scripts/tests/run.sh 2>&1 | tail -10
```

Expected: `ALL ASSERTIONS PASS`.

```bash
git add scripts/tests/
git commit -m "test(scripts): sh assertions — syntax + pid helpers + migrate dry-run"
```

### Task 28: Sprint-7 verification gate

- [ ] **Step 1: All 4 pkg + scripts test**

```bash
cd /mnt/d/github/cf
bash scripts/test.sh 2>&1 | tail -10
bash scripts/tests/run.sh 2>&1 | tail -5
```

Expected: ALL PASS for both.

---

## Sprint 8 — Remove camfit-puller/ husk

**Goal:** delete remaining empty/legacy folders + files in camfit-puller/.

### Task 29: Identify remaining files in camfit-puller/

- [ ] **Step 1: Inventory**

```bash
cd /mnt/d/github/cf
find camfit-puller -type f 2>&1
```

Expected files:
- `pyproject.toml` (no longer needed)
- `README.md` (content moved to backend/README.md or delete)
- `__init__.py` files in src/
- Any test conftest.py not yet moved
- Any other tracked files

- [ ] **Step 2: Decide each remainder**

For each file:
- `pyproject.toml` → delete.
- `README.md` → delete (content in backend/README.md).
- `src/camfit_puller/__init__.py` → delete (package fully migrated).
- `tests/conftest.py` if exists → move to backend/tests/conftest.py (likely backend integration setup).
- `tests/__init__.py` → delete (backend/tests/__init__.py already in place).
- Any leftover __pycache__/ — already gitignored.

- [ ] **Step 3: Inspect tests/conftest.py if present**

```bash
test -f camfit-puller/tests/conftest.py && head -20 camfit-puller/tests/conftest.py || echo "no conftest"
```

If exists and content is backend-related (DB fixture, etc.):
```bash
git mv camfit-puller/tests/conftest.py backend/tests/conftest.py
```

If content is empty/trivial, delete.

### Task 30: Delete husk

- [ ] **Step 1: Move conftest.py if present (per Task 29 step 3)**

(Skip if no conftest.)

- [ ] **Step 2: Remove all camfit-puller files**

```bash
git rm -r camfit-puller/
git status --short | head -10
```

- [ ] **Step 3: Verify directory is gone**

```bash
test -d camfit-puller && echo "STILL EXISTS — FIX" || echo "removed cleanly"
```

- [ ] **Step 4: Remove from .gitignore if it had a per-camfit-puller entry**

```bash
grep "camfit-puller" .gitignore || echo "clean"
```

If matched, edit to remove.

- [ ] **Step 5: Commit removal**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: remove camfit-puller/ husk after full split

All code migrated:
- crawler core → crawl/camfit/
- backend (FastAPI + clean-arch) → backend/
- pipeline scripts → pipeline/
- data → crawl/camfit/data
- crawler tests → crawl/camfit/tests
- backend tests → backend/tests

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 31: Sprint-8 verification gate

- [ ] **Step 1: All packages still pass**

```bash
bash scripts/test.sh 2>&1 | tail -10
```

Expected: ALL PASS.

- [ ] **Step 2: camfit-puller/ gone**

```bash
test -d camfit-puller && echo "FAIL" || echo "OK"
```

Expected: `OK`.

- [ ] **Step 3: git history preserved (spot check)**

```bash
git log --follow --oneline backend/src/cf_backend/api.py | head -5
git log --follow --oneline crawl/camfit/src/camfit_crawl/crawler.py | head -5
```

Expected: log shows commits before the moves (rename detection working).

---

## Sprint 9 — Integration smoke

**Goal:** end-to-end verification. setup → crawl → migrate dry-run → teardown.

### Task 32: End-to-end smoke

- [ ] **Step 1: Clean state check**

```bash
cd /mnt/d/github/cf
git status --short
```

Expected: empty (or only `.run/` content which is gitignored).

- [ ] **Step 2: uv sync from clean**

```bash
rm -rf .venv
uv sync 2>&1 | tail -5
```

Expected: 0 errors.

- [ ] **Step 3: db-up smoke (requires docker)**

If docker available:
```bash
bash scripts/db-up.sh 2>&1 | tail -10
bash scripts/db-status.sh 2>&1 | tail -5
```

Expected: `both healthy after Ns`. If no docker → SKIP this step, document in handoff.

- [ ] **Step 4: txcp crawl smoke (live network)**

```bash
bash scripts/crawl-txcp.sh --site-tp BB000 --max-pages 2 2>&1 | tail -10
```

Expected: `pages_fetched: 2`, jsonl + csv created at `crawl/txcp/data/`.

- [ ] **Step 5: migrate dry-run**

```bash
bash scripts/migrate.sh --dry-run 2>&1 | tail -15
```

Expected: 5-stage plan + `DRY RUN — no execution`. Exit 0.

- [ ] **Step 6: All package pytest**

```bash
bash scripts/test.sh 2>&1 | tail -15
```

Expected: ALL PASS.

- [ ] **Step 7: teardown**

```bash
bash scripts/teardown.sh 2>&1 | tail -5
```

Expected: backend stopped + db down.

- [ ] **Step 8: Final commit (no changes expected; just verify clean state)**

```bash
git status --short
```

Expected: empty.

### Task 33: Final commit + push

- [ ] **Step 1: Update root README (if exists) with link to spec**

If `D:\github\cf\README.md` exists, add a brief paragraph pointing to the new layout + spec doc. If not, skip.

```bash
test -f README.md && head -5 README.md || echo "no root README"
```

If you want to create or update — keep tiny:
```markdown
# cf

uv workspace: `crawl/camfit`, `crawl/txcp`, `backend`, `pipeline`. Ops via `scripts/`. Spec: [`docs/superpowers/specs/2026-05-10-repo-restructure-design.md`](docs/superpowers/specs/2026-05-10-repo-restructure-design.md).
```

- [ ] **Step 2: Push**

```bash
git push origin main
```

Expected: 0 errors. Sprint commits land on origin/main.

---

## Rollback Strategy

Each sprint commits independently. If a sprint breaks the gate (pytest fail, smoke fail), rollback is `git reset --hard HEAD~N` where N = commit count of that sprint. The pre-flight tag `pre-restructure-YYYYMMDD` allows reset to the absolute starting state if needed.

| Sprint | Commits in sprint | Rollback if fail |
|---|---|---|
| S1 | 1 (workspace root) | `git reset --hard HEAD~1` |
| S2 | 2 (mv + rename) | `git reset --hard HEAD~2` |
| S3 | 4 (scaffold + 3 module/script/test moves) | `git reset --hard HEAD~4` |
| S4 | 1 (data move) or 0 (untracked) | `git reset --hard HEAD~1` (or no-op) |
| S5 | 3 (scaffold + module + tests) | `git reset --hard HEAD~3` |
| S6 | 4 (scaffold + scripts + full_run + adapter) | `git reset --hard HEAD~4` |
| S7 | 6 (lib + db + backend + crawl + setup + tests) | `git reset --hard HEAD~6` |
| S8 | 1 (husk removal) | `git reset --hard HEAD~1` |
| S9 | 0 or 1 (verification only) | n/a |

Absolute reset: `git reset --hard pre-restructure-YYYYMMDD`.

---

## Appendix: Why each rewrite is safe

- **`from camfit_puller.X import Y` → `from cf_backend.X import Y`** (only for backend): backend modules' clean-arch internal imports stay relative within their layer. The sed rewrite is for the entry-point (api.py, container.py, tests) which used absolute imports.
- **`from camfit_puller.X import Y` → `from camfit_crawl.X import Y`** (for crawler subset): same logic. Pre-flight grep confirmed src/ uses relative imports, so the rewrite touches scripts + tests only.
- **uv workspace path resolution**: `[tool.uv.sources] cf-backend = { workspace = true }` resolves to `backend/` member at install time. pipeline imports `cf_backend.X` work as if cf-backend were a regular wheel.

## Appendix: Commands reference (Windows native)

If running on Windows PowerShell instead of WSL bash:
- Replace `/mnt/d/github/cf` with `D:\github\cf`.
- Replace `bash scripts/X.sh` with `wsl bash scripts/X.sh` (sh-only per spec).
- `sed -i` works in WSL bash; native PowerShell needs `Get-Content | %{$_ -replace ...} | Set-Content` (not used in this plan; run all sed via WSL bash).
