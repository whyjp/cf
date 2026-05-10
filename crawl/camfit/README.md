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
