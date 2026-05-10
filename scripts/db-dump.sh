#!/usr/bin/env bash
# Dump postgres + falkordb to seed dir (default: seed/latest/).
#
# Output:
#   $SEED_DIR/postgres.dump   pg_dump custom format (compressed)
#   $SEED_DIR/falkor.rdb      Redis RDB snapshot
#   $SEED_DIR/manifest.json   schema + counts + timestamp + embed model
#
# Idempotent: re-run replaces the seed dir contents.
#
# Usage:
#   scripts/db-dump.sh                           # → seed/latest/
#   scripts/db-dump.sh seed/2026-05-10/          # explicit dir
#   SEED_DIR=/some/path scripts/db-dump.sh
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

SEED_DIR="${1:-${SEED_DIR:-$REPO_ROOT/seed/latest}}"
mkdir -p "$SEED_DIR"

log_info "dump target: $SEED_DIR"

# ─── postgres ────────────────────────────────────────────────────────────
log_info "[1/3] pg_dump (custom format, compressed)"
docker exec camfit-postgres pg_dump -U camfit -d camfit -F c \
    > "$SEED_DIR/postgres.dump"
pg_size=$(stat -c %s "$SEED_DIR/postgres.dump" 2>/dev/null || stat -f %z "$SEED_DIR/postgres.dump")
log_info "  postgres.dump = $pg_size bytes"

# ─── falkor ──────────────────────────────────────────────────────────────
log_info "[2/3] falkor SAVE + RDB copy"
docker exec camfit-falkordb redis-cli SAVE >/dev/null
docker cp camfit-falkordb:/var/lib/falkordb/data/dump.rdb "$SEED_DIR/falkor.rdb"
falkor_size=$(stat -c %s "$SEED_DIR/falkor.rdb" 2>/dev/null || stat -f %z "$SEED_DIR/falkor.rdb")
log_info "  falkor.rdb = $falkor_size bytes"

# ─── manifest ────────────────────────────────────────────────────────────
log_info "[3/3] manifest.json"
camps_total=$(docker exec camfit-postgres psql -U camfit -d camfit -tAc \
    "SELECT count(*) FROM camps")
camps_camfit=$(docker exec camfit-postgres psql -U camfit -d camfit -tAc \
    "SELECT count(*) FROM camps WHERE source='camfit'")
camps_txcp=$(docker exec camfit-postgres psql -U camfit -d camfit -tAc \
    "SELECT count(*) FROM camps WHERE source='txcp'")
embeddings=$(docker exec camfit-postgres psql -U camfit -d camfit -tAc \
    "SELECT count(*) FROM camp_embeddings")
embed_model=$(docker exec camfit-postgres psql -U camfit -d camfit -tAc \
    "SELECT model_name FROM camp_embeddings LIMIT 1" 2>/dev/null || echo "unknown")
falkor_nodes=$(docker exec camfit-falkordb redis-cli GRAPH.QUERY camfit \
    "MATCH (n) RETURN count(n)" 2>/dev/null | sed -n 's/.*"\([0-9]*\)".*/\1/p' | head -1)
schema_rev=$(docker exec camfit-postgres psql -U camfit -d camfit -tAc \
    "SELECT version_num FROM alembic_version" 2>/dev/null || echo "unknown")

cat > "$SEED_DIR/manifest.json" <<EOF
{
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "schema_rev": "$schema_rev",
  "embed_model": "$embed_model",
  "files": {
    "postgres.dump": $pg_size,
    "falkor.rdb": $falkor_size
  },
  "counts": {
    "camps_total": ${camps_total:-0},
    "camps_camfit": ${camps_camfit:-0},
    "camps_txcp": ${camps_txcp:-0},
    "camp_embeddings": ${embeddings:-0},
    "falkor_nodes": ${falkor_nodes:-0}
  }
}
EOF

log_info "DONE"
log_info "  total: $((pg_size + falkor_size)) bytes ($SEED_DIR)"
cat "$SEED_DIR/manifest.json"
