#!/usr/bin/env bash
# Load seed dump into running postgres + falkordb. Run on first deploy.
#
# Idempotent: detects existing data and SKIPS load unless --force given.
# Detection: camps table count > 0 OR sentinel file ($RUN_DIR/seed-loaded).
#
# Pre-requisite: scripts/db-up.sh has been run (containers + DB schema initialised
# via alembic upgrade head). camps table can be empty — seed will populate it.
#
# Usage:
#   scripts/db-seed-load.sh                      # default seed/latest/
#   scripts/db-seed-load.sh seed/2026-05-10/     # explicit dir
#   scripts/db-seed-load.sh --force              # skip empty-check, overwrite
#   SEED_DIR=/some/path scripts/db-seed-load.sh
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

FORCE=0
SEED_DIR="${SEED_DIR:-$REPO_ROOT/seed/latest}"
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        -*) log_error "unknown flag: $arg"; exit 1 ;;
        *) SEED_DIR="$arg" ;;
    esac
done

if [ ! -d "$SEED_DIR" ]; then
    log_error "seed dir not found: $SEED_DIR"
    log_error "  run scripts/db-dump.sh first on the dev box, then ship the dir to prod."
    exit 1
fi
if [ ! -f "$SEED_DIR/postgres.dump" ] || [ ! -f "$SEED_DIR/falkor.rdb" ]; then
    log_error "seed dir missing files: postgres.dump and/or falkor.rdb"
    log_error "  contents of $SEED_DIR:"
    ls -la "$SEED_DIR" >&2 || true
    exit 1
fi

# ─── idempotency: detect already-loaded ──────────────────────────────────
SENTINEL="$RUN_DIR/seed-loaded"
if [ "$FORCE" -eq 0 ]; then
    if [ -f "$SENTINEL" ]; then
        log_info "seed already loaded (sentinel: $SENTINEL). pass --force to override."
        cat "$SENTINEL"
        exit 0
    fi
    # Belt + braces: also check camps table count (alembic-created table).
    cur_count=$(docker exec camfit-postgres psql -U camfit -d camfit -tAc \
        "SELECT count(*) FROM camps" 2>/dev/null || echo "0")
    if [ "${cur_count:-0}" -gt "0" ]; then
        log_info "DB already has $cur_count camps — skip seed load. pass --force to override."
        exit 0
    fi
fi

log_info "loading seed from: $SEED_DIR"
[ -f "$SEED_DIR/manifest.json" ] && log_info "manifest: $(cat "$SEED_DIR/manifest.json" | tr -d '\n' | head -c 300)"

# ─── postgres restore ────────────────────────────────────────────────────
log_info "[1/3] pg_restore (--clean --if-exists)"
docker cp "$SEED_DIR/postgres.dump" camfit-postgres:/tmp/seed.dump
docker exec camfit-postgres pg_restore \
    -U camfit -d camfit --clean --if-exists --no-owner --no-acl \
    /tmp/seed.dump || {
        log_error "pg_restore failed"
        docker exec camfit-postgres rm -f /tmp/seed.dump || true
        exit 1
    }
docker exec camfit-postgres rm -f /tmp/seed.dump

# ─── falkor restore ──────────────────────────────────────────────────────
log_info "[2/3] falkor RDB swap + restart"
docker cp "$SEED_DIR/falkor.rdb" camfit-falkordb:/var/lib/falkordb/data/dump.rdb
docker restart camfit-falkordb >/dev/null
log_info "  waiting for falkor healthy..."
for i in $(seq 1 30); do
    if docker exec camfit-falkordb redis-cli ping 2>/dev/null | grep -q PONG; then
        log_info "  falkor up after ${i}s"
        break
    fi
    sleep 1
done

# ─── sentinel + verification ─────────────────────────────────────────────
log_info "[3/3] sentinel + verify"
camps=$(docker exec camfit-postgres psql -U camfit -d camfit -tAc "SELECT count(*) FROM camps")
nodes=$(docker exec camfit-falkordb redis-cli GRAPH.QUERY camfit "MATCH (n) RETURN count(n)" 2>/dev/null | sed -n 's/.*"\([0-9]*\)".*/\1/p' | head -1)
embeddings=$(docker exec camfit-postgres psql -U camfit -d camfit -tAc "SELECT count(*) FROM camp_embeddings")

cat > "$SENTINEL" <<EOF
{
  "loaded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "seed_dir": "$SEED_DIR",
  "post_load_counts": {
    "camps": ${camps:-0},
    "camp_embeddings": ${embeddings:-0},
    "falkor_nodes": ${nodes:-0}
  }
}
EOF

log_info "DONE"
cat "$SENTINEL"
