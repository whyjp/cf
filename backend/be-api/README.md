# cf-be-api

FastAPI + clean-arch backend (DB-tier). Migrated from `camfit-puller/src/camfit_puller/{api,container,domain,ports,usecases,adapters}`, then renamed from `cf-backend` (SP-A sprint A1).

## Layers
- `domain/` — entities, errors, value objects (no IO).
- `ports/` — abstract interfaces (Repo, Graph, Source, Embed, etc.).
- `usecases/` — application services orchestrating ports.
- `adapters/` — concrete impls (falkor, postgres, pgvector, etago_bin, ...).
- `api.py` — FastAPI surface.
- `container.py` — DI wiring.

## Run

```sh
uv run --package cf-be-api uvicorn cf_be_api.api:app --reload
```

## DB
- falkordb 6379 + postgres 5432 via `docker/docker-compose.yml`. Use `scripts/db-up.sh`.
