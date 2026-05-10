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

## Admin / graph endpoints

`/admin/*` 와 `/graph/*` 는 be-api 에만 존재. BFF (`cf-be-for-fe`) 는 이들을
노출하지 않는다. 어드민 도구 (예: `fe/public/graph.html`) 는 직접 be-api
호스트로 호출한다:

```
http://admin.internal:8071/graph/sample?...
```

`fe/public/graph.html` 의 `?api=` 쿼리로 base URL 주입 가능:

```
fe/public/graph.html?api=http://admin.internal:8071
```

VPC 내부 또는 사내망 접근 가정. 외부 인터넷 노출 금지 — SG/firewall 로 차단.
