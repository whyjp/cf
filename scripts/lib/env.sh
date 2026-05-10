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

# be-api / be-for-fe split (SP-A) -- prefer dev-up.sh over backend-up.sh.
# BACKEND_* above kept for backwards-compat only.
export BE_API_HOST="${BE_API_HOST:-127.0.0.1}"
export BE_API_PORT="${BE_API_PORT:-8071}"
export BE_API_PID_FILE="$RUN_DIR/be-api.pid"
export BE_API_LOG_FILE="$RUN_DIR/be-api.log"

export BFF_HOST="${BFF_HOST:-0.0.0.0}"
export BFF_PORT="${BFF_PORT:-8070}"
export BFF_PID_FILE="$RUN_DIR/bff.pid"
export BFF_LOG_FILE="$RUN_DIR/bff.log"

# uv binary detection -- WSL doesn't auto-resolve .exe
if command -v uv >/dev/null 2>&1; then
    export UV=uv
elif command -v uv.exe >/dev/null 2>&1; then
    export UV=uv.exe
else
    echo "[env.sh] ERROR: uv not found in PATH" >&2
    exit 1
fi

# SP-D D-8 cutover (2026-05-11): be-api is the Go binary at backend/be-api/.
# DLLs (mingw runtime + onnxruntime) live next to the .exe; assets-onnx/ holds
# ko-sroberta + tokenizer.
export BE_API_BIN="$REPO_ROOT/backend/be-api/be-api.exe"

# Locate Windows-installed mingw64 + Go from either Git Bash (/c/...) or WSL
# (/mnt/c/...). Exported so dev-up.sh build_be_api can find them.
for _mingw in /c/msys64/mingw64/bin /mnt/c/msys64/mingw64/bin; do
    if [ -d "$_mingw" ]; then
        export MINGW64_BIN="$_mingw"
        break
    fi
done
# `go` discovery for both Git Bash (sees go.exe as "go") and WSL bash (which
# does NOT auto-strip .exe — `command -v go` returns 1 even when go.exe is on
# PATH). Probe for either name; alias with GO_BIN so dev-up.sh can call it
# directly without ambiguity.
if command -v go >/dev/null 2>&1; then
    export GO_BIN=go
elif command -v go.exe >/dev/null 2>&1; then
    export GO_BIN=go.exe
else
    # bash `for` word-splits on spaces even inside quotes (legacy POSIX).
    # Use an array so paths with spaces survive.
    _go_candidates=(
        "/c/Program Files/Go/bin"
        "/mnt/c/Program Files/Go/bin"
    )
    for _go in "${_go_candidates[@]}"; do
        if [ -x "$_go/go.exe" ]; then
            export PATH="$_go:$PATH"
            export GO_BIN=go.exe
            break
        elif [ -x "$_go/go" ]; then
            export PATH="$_go:$PATH"
            export GO_BIN=go
            break
        fi
    done
    : "${GO_BIN:=go}"  # last-resort default; fail later with a clearer message
fi
