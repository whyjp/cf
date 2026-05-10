#!/usr/bin/env bash
# Push seed dump to a remote managed Postgres (Render / Supabase / RDS / etc).
#
# Required: $DATABASE_URL (or first arg) connection string.
#   Render:    postgresql://USER:PASS@HOST.render.com/DB?sslmode=require
#   Supabase:  postgresql://postgres:PASS@db.PROJ.supabase.co:5432/postgres
#   Generic:   postgresql://...
#
# Pre-requisites on the target:
#   - pgvector extension installable (Render auto / Supabase enable in dashboard).
#   - The role in DATABASE_URL has CREATE / DROP rights on its schema.
#
# Idempotent: --clean --if-exists drops + recreates the schema objects.
# Safe to re-run; managed-service-friendly (--no-owner --no-acl strips local
# ownership references that don't exist in the cloud).
#
# Usage:
#   DATABASE_URL=postgresql://... bash scripts/db-seed-load-url.sh
#   bash scripts/db-seed-load-url.sh "postgresql://..."
#   bash scripts/db-seed-load-url.sh seed/2026-05-10/   # alt seed dir, $DATABASE_URL must be set
#
# falkordb is NOT pushed by this script — managed Postgres services don't run
# Redis-compatible falkordb. For graph features in production: run falkor
# separately (own VM/container) and load seed/latest/falkor.rdb there.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

# Parse args: first non-flag arg is either URL or seed dir
URL="${DATABASE_URL:-}"
SEED_DIR="${SEED_DIR:-$REPO_ROOT/seed/latest}"
for arg in "$@"; do
    case "$arg" in
        postgres://*|postgresql://*) URL="$arg" ;;
        -*) log_error "unknown flag: $arg"; exit 1 ;;
        *) SEED_DIR="$arg" ;;
    esac
done

if [ -z "$URL" ]; then
    log_error "DATABASE_URL not set (also accepts URL as positional arg)"
    log_error "  Render:   postgresql://USER:PASS@HOST.render.com/DB?sslmode=require"
    log_error "  Supabase: postgresql://postgres:PASS@db.PROJ.supabase.co:5432/postgres"
    exit 1
fi
if [ ! -f "$SEED_DIR/postgres.dump" ]; then
    log_error "seed dump not found: $SEED_DIR/postgres.dump"
    log_error "  run scripts/db-dump.sh first."
    exit 1
fi

log_info "target: ${URL//:*@/:***@}"   # mask password in log
log_info "seed:   $SEED_DIR/postgres.dump"

# ─── pre-flight: ensure required extensions exist on target ──────────────
log_info "[1/4] pre-create extensions (vector, pg_trgm) — idempotent"
"$UV" run --package cf-be-api python -c "
import os, psycopg
url = os.environ['DATABASE_URL']
with psycopg.connect(url) as conn, conn.cursor() as cur:
    cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
    cur.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    conn.commit()
    print('  extensions ready')
" || {
    log_error "extension creation failed — check role privileges"
    log_error "  Supabase: enable 'vector' in Database > Extensions before running."
    exit 1
}

# ─── pre-flight: idempotency check ───────────────────────────────────────
log_info "[2/4] check target state"
existing=$("$UV" run --package cf-be-api python -c "
import os, psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as conn, conn.cursor() as cur:
    try:
        cur.execute('SELECT count(*) FROM camps')
        print(cur.fetchone()[0])
    except Exception:
        print(0)
" 2>/dev/null | tail -1 | tr -d '[:space:]')
existing="${existing:-0}"
if [ "$existing" -gt "0" ] && [ "${FORCE:-0}" != "1" ]; then
    log_info "target already has $existing camps — skip. set FORCE=1 to override."
    exit 0
fi

# ─── pg_restore via dockerised postgres:16 client ────────────────────────
log_info "[3/4] pg_restore --clean --if-exists --no-owner --no-acl"
# Use postgres:16 image as a portable pg_restore client (avoids requiring
# pg_restore on the host PATH). The dump is piped on stdin.
docker run --rm -i \
    -e PGSSLMODE=require \
    postgres:16 \
    pg_restore -d "$URL" \
        --clean --if-exists --no-owner --no-acl --verbose \
    < "$SEED_DIR/postgres.dump" 2>&1 | tail -20

# pg_restore returns non-zero on certain warnings (FK/role/etc). Verify by count.

# ─── verify ──────────────────────────────────────────────────────────────
log_info "[4/4] verify"
"$UV" run --package cf-be-api python -c "
import os, psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as conn, conn.cursor() as cur:
    for q in [
        ('camps total',    'SELECT count(*) FROM camps'),
        ('camps camfit',   \"SELECT count(*) FROM camps WHERE source='camfit'\"),
        ('camps txcp',     \"SELECT count(*) FROM camps WHERE source='txcp'\"),
        ('camp_embeddings','SELECT count(*) FROM camp_embeddings'),
        ('alembic rev',    'SELECT version_num FROM alembic_version'),
    ]:
        try:
            cur.execute(q[1])
            print(f'  {q[0]:18s}{cur.fetchone()[0]}')
        except Exception as e:
            print(f'  {q[0]:18s}ERR {e}')
"

log_info "DONE — falkor side requires separate deploy (managed Postgres has no falkor)"
