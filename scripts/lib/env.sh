#!/usr/bin/env bash
# scripts/lib/env.sh -- shared env. source this from every script.

set -euo pipefail

# Repo root -- env override or compute from this script's location
if [ -z "${REPO_ROOT:-}" ]; then
    _here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="$(cd "$_here/../.." && pwd)"
fi
export REPO_ROOT

export RUN_DIR="$REPO_ROOT/.run"
mkdir -p "$RUN_DIR"

export CAMFIT_DATA="$REPO_ROOT/crawl/camfit/data"
export TXCP_DATA="$REPO_ROOT/crawl/txcp/data"

export DATABASE_URL="${DATABASE_URL:-postgresql://camfit:camfit@localhost:5432/camfit}"
export FALKORDB_URL="${FALKORDB_URL:-redis://localhost:6379}"

export BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
export BACKEND_PORT="${BACKEND_PORT:-8000}"
export BACKEND_PID_FILE="$RUN_DIR/backend.pid"
export BACKEND_LOG_FILE="$RUN_DIR/backend.log"

# uv binary detection -- WSL doesn't auto-resolve .exe
if command -v uv >/dev/null 2>&1; then
    export UV=uv
elif command -v uv.exe >/dev/null 2>&1; then
    export UV=uv.exe
else
    echo "[env.sh] ERROR: uv not found in PATH" >&2
    exit 1
fi
