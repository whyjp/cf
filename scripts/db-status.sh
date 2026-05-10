#!/usr/bin/env bash
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT/docker"
docker compose ps
echo "---"
docker compose exec -T falkordb redis-cli ping || log_warn "falkordb not responding"
docker compose exec -T postgres pg_isready -U camfit -d camfit || log_warn "postgres not ready"
