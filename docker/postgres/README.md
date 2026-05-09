# PostgreSQL + pgvector Docker

Isolated PostgreSQL 16 + pgvector service for camfit-puller.

## Bring Up

```bash
wsl -e bash -c "cd /mnt/d/github/cf/docker/postgres && docker compose up -d"
```

## Details

- **Port:** 5432
- **User:** camfit
- **Password:** camfit
- **Database:** camfit
- **Extensions:** pgvector, pg_trgm (auto-installed)

## Stop / Reset

```bash
docker compose down          # container only (data persists)
docker compose down -v       # also remove pg_data volume (full reset)
```
