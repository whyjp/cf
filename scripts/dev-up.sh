#!/usr/bin/env bash
# Start be-api (Go) + be-for-fe (Python) in background. PIDs to .run/.
# SP-D D-8 cutover (2026-05-11): be-api is now the Go binary at backend/be-api/.
# Build step also bundles mingw64 runtime DLLs (cgo dependency for ONNX).
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

build_be_api() {
    log_info "building be-api Go binary"
    local mingw="${MINGW64_BIN:-}"
    if [ -z "$mingw" ] || [ ! -d "$mingw" ]; then
        log_warn "MSYS2 mingw64 not found (looked at /c/msys64/mingw64/bin and /mnt/c/...)"
        log_warn "install: https://www.msys2.org/ then 'pacman -S mingw-w64-x86_64-gcc'"
    fi
    # WSL → Windows env-var forwarding requires WSLENV. Without it, the
    # Windows go.exe sees CGO_ENABLED=0 (its default) and PATH stripped of
    # the mingw addition. Git Bash on Windows ignores WSLENV (no harm).
    #
    # Tricky bits:
    #   - CC=gcc.exe (not "gcc") — WSL has /usr/bin/gcc (Linux ELF, wrong for
    #     Windows builds). We tell cgo to use mingw's gcc.exe explicitly.
    #   - WSLENV "PATH/l" tells WSL to translate the WSL PATH (with /mnt/c/...
    #     prefixes) into Windows-style paths (C:\...) when handing off to
    #     go.exe — that way gcc.exe in mingw is discoverable on the Windows
    #     side.
    if ! (cd "$REPO_ROOT/backend/be-api" && \
          WSLENV="CGO_ENABLED:CC:CXX:PATH/l:${WSLENV:-}" \
          PATH="$mingw:$PATH" CGO_ENABLED=1 CC=gcc.exe CXX=g++.exe \
          "${GO_BIN:-go}" build -o be-api.exe ./cmd/be-api); then
        log_error "be-api Go build failed"
        return 1
    fi

    # Bundle mingw64 runtime DLLs (cgo + onnxruntime tags need them at runtime).
    for dll in libgcc_s_seh-1.dll libwinpthread-1.dll libstdc++-6.dll; do
        if [ ! -f "$REPO_ROOT/backend/be-api/$dll" ]; then
            if [ -n "$mingw" ] && [ -f "$mingw/$dll" ]; then
                cp "$mingw/$dll" "$REPO_ROOT/backend/be-api/"
                log_info "bundled mingw runtime: $dll"
            else
                log_warn "missing mingw DLL: $dll (be-api may fail to start)"
            fi
        fi
    done

    # ONNX runtime DLL — one-time manual fetch. Embedder runs in nil-mode if
    # missing (semantic_search returns 503 only; rest of the API still works).
    if [ ! -f "$REPO_ROOT/backend/be-api/onnxruntime.dll" ]; then
        log_warn "onnxruntime.dll not in backend/be-api/ — embedder will be nil"
        log_warn "fetch: https://github.com/microsoft/onnxruntime/releases/download/v1.20.1/onnxruntime-win-x64-1.20.1.zip"
        log_warn "and copy lib/onnxruntime.dll into backend/be-api/"
    fi
}

start_be_api() {
    if [ -f "$BE_API_PID_FILE" ] && pid_alive "$(cat "$BE_API_PID_FILE")"; then
        log_warn "be-api already running (pid $(cat "$BE_API_PID_FILE"))"
        return 0
    fi
    [ -f "$BE_API_PID_FILE" ] && rm -f "$BE_API_PID_FILE"

    if [ ! -x "$BE_API_BIN" ]; then
        build_be_api || return 1
    fi

    log_info "starting be-api (Go) on $BE_API_HOST:$BE_API_PORT"
    cd "$REPO_ROOT/backend/be-api"
    # WSLENV — every var the Windows be-api.exe needs to see. Without this
    # forwarding list, WSL strips them on the bash → Windows-process boundary
    # (config defaults take over, e.g. embedder=nil + port=default).
    #
    # WSLENV flags:
    #   /p — translate single Linux path → Windows path (D:\...)
    #   /l — translate list of paths (PATH-like)
    # ONNX path vars must be /p so the Windows process gets D:\...\onnxruntime.dll
    # (not /mnt/d/... which is meaningless on the Windows side).
    DATABASE_URL="$DATABASE_URL" \
    FALKORDB_URL="$FALKORDB_URL" \
    NAVER_NCP_CLIENT_ID="${NAVER_NCP_CLIENT_ID:-}" \
    NAVER_NCP_CLIENT_SECRET="${NAVER_NCP_CLIENT_SECRET:-}" \
    KAKAO_REST_KEY="${KAKAO_REST_KEY:-}" \
    ONNXRUNTIME_LIB="$REPO_ROOT/backend/be-api/onnxruntime.dll" \
    KO_SROBERTA_ONNX="$REPO_ROOT/backend/be-api/assets-onnx/ko-sroberta.onnx" \
    KO_SROBERTA_TOKENIZER="$REPO_ROOT/backend/be-api/assets-onnx/tokenizer.json" \
    BE_API_HOST="$BE_API_HOST" \
    BE_API_PORT="$BE_API_PORT" \
    WSLENV="DATABASE_URL:FALKORDB_URL:NAVER_NCP_CLIENT_ID:NAVER_NCP_CLIENT_SECRET:KAKAO_REST_KEY:ONNXRUNTIME_LIB/p:KO_SROBERTA_ONNX/p:KO_SROBERTA_TOKENIZER/p:BE_API_HOST:BE_API_PORT:${WSLENV:-}" \
    nohup ./be-api.exe > "$BE_API_LOG_FILE" 2>&1 &
    write_pid "$BE_API_PID_FILE" "$!"
    log_info "be-api pid $! -- log: $BE_API_LOG_FILE"
}

start_bff() {
    if [ -f "$BFF_PID_FILE" ] && pid_alive "$(cat "$BFF_PID_FILE")"; then
        log_warn "bff already running (pid $(cat "$BFF_PID_FILE"))"
        return 0
    fi
    [ -f "$BFF_PID_FILE" ] && rm -f "$BFF_PID_FILE"
    log_info "starting be-for-fe on $BFF_HOST:$BFF_PORT (upstream http://${BE_API_HOST}:${BE_API_PORT})"
    cd "$REPO_ROOT"
    BFF_BE_API_BASE_URL="http://${BE_API_HOST}:${BE_API_PORT}" \
        nohup "$UV" run --package cf-be-for-fe uvicorn cf_be_for_fe.api:app \
        --host "$BFF_HOST" --port "$BFF_PORT" \
        > "$BFF_LOG_FILE" 2>&1 &
    write_pid "$BFF_PID_FILE" "$!"
    log_info "bff pid $! -- log: $BFF_LOG_FILE"
}

start_be_api
sleep 2
# healthz polling -- be-api
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf "http://${BE_API_HOST}:${BE_API_PORT}/healthz" >/dev/null 2>&1; then
        log_info "be-api ready"
        break
    fi
    sleep 0.5
done

start_bff
# healthz polling -- bff (use 127.0.0.1 to dial when host is 0.0.0.0)
_bff_dial="${BFF_HOST}"
[ "$_bff_dial" = "0.0.0.0" ] && _bff_dial="127.0.0.1"
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf "http://${_bff_dial}:${BFF_PORT}/healthz" >/dev/null 2>&1; then
        log_info "bff ready"
        break
    fi
    sleep 0.5
done

log_info "logs: $BE_API_LOG_FILE  $BFF_LOG_FILE"
log_info "fallback (D-8 cutover failure): git revert <merge sha>; uv sync; ./scripts/dev-up.sh"
