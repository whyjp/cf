# cf-pipeline

Post-crawl orchestration:
1. `ingest_camps` — `crawl/{camfit,txcp}/data/*.jsonl` → postgres `camps` (upsert).
2. `geocode_run` — null lat/lon → etago binary → UPDATE.
3. `rebuild_graph` — postgres → falkor.
4. `derive_lexicon` — keyword/synonym dict.
5. `seed_concepts` / `seed_filter_mapping` — themes + filter mapping.

## Run

```sh
uv run --package cf-pipeline python -m cf_pipeline.full_run --help
```

Or via `scripts/migrate.sh`.
