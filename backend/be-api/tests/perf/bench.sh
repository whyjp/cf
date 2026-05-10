#!/usr/bin/env bash
# SP-D D-7 perf bench: side-by-side latency comparison Python vs Go be-api.
#
# Usage:
#   ./tests/perf/bench.sh                      # default N=20 samples per call
#   N=50 PY=http://localhost:8071 GO=http://127.0.0.1:8073 ./bench.sh
#   ./tests/perf/bench.sh > /tmp/perf.log      # capture for docs/sp-d-performance-baseline.md
#
# Output: one block per endpoint with avg/min/max from N curl --time_total samples.
#         Final summary table is suitable for direct paste into the perf doc.
set -euo pipefail

PY="${PY:-http://localhost:8071}"
GO="${GO:-http://127.0.0.1:8073}"
N="${N:-20}"

# Probe both sides — abort early with a clear message if either is down.
if ! curl -sf "$PY/healthz" >/dev/null 2>&1; then
    echo "FATAL: Python be-api unreachable at $PY/healthz"
    exit 1
fi
if ! curl -sf "$GO/healthz" >/dev/null 2>&1; then
    echo "FATAL: Go be-api unreachable at $GO/healthz"
    exit 1
fi

echo "## SP-D D-7 perf bench"
echo "PY=$PY"
echo "GO=$GO"
echo "N=$N"
echo "host: $(hostname 2>/dev/null || echo unknown)  date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

# Stash sample IDs once for /eta/batch later.
IDS_JSON=$(curl -s "$GO/sites?limit=10" \
    | python3 -c "import sys,json; rows=json.load(sys.stdin); print(json.dumps([r['id'] for r in rows[:10]]))" \
    2>/dev/null || echo "[]")

# bench_get NAME PATH — measures GET latency.
bench_get() {
    local name=$1 path=$2
    echo "=== $name [$path] ==="
    for base in "$PY" "$GO"; do
        local label=${base##*//}
        printf "  %-30s " "$label"
        for _ in $(seq 1 "$N"); do
            curl -s -o /dev/null -w "%{time_total}\n" "$base$path"
        done | awk 'BEGIN{s=0; mn=999; mx=0}{s+=$1; if($1<mn)mn=$1; if($1>mx)mx=$1}END{printf "avg=%.4fs  min=%.4fs  max=%.4fs  (n=%d)\n", s/NR, mn, mx, NR}'
    done
    echo
}

# bench_post NAME PATH BODY (smaller N — POSTs are usually heavier).
bench_post() {
    local name=$1 path=$2 body=$3
    local n=$((N / 4))
    if [ "$n" -lt 3 ]; then n=3; fi
    echo "=== $name [POST $path] (n=$n) ==="
    for base in "$PY" "$GO"; do
        local label=${base##*//}
        printf "  %-30s " "$label"
        for _ in $(seq 1 "$n"); do
            curl -s -X POST -H "Content-Type: application/json" -d "$body" \
                -o /dev/null -w "%{time_total}\n" "$base$path"
        done | awk 'BEGIN{s=0; mn=999; mx=0}{s+=$1; if($1<mn)mn=$1; if($1>mx)mx=$1}END{printf "avg=%.4fs  min=%.4fs  max=%.4fs  (n=%d)\n", s/NR, mn, mx, NR}'
    done
    echo
}

# Read endpoints
bench_get "sites_default"           "/sites"
bench_get "sites_region_gangwon"    "/sites?region=강원"
bench_get "sites_concept_valley"    "/sites?concept=valley"
bench_get "facets"                  "/facets"
bench_get "featured_axes"           "/featured-axes"
bench_get "concepts"                "/concepts"
bench_get "themes"                  "/themes"
bench_get "marks"                   "/marks"
bench_get "sites_search_gangwon"    "/sites/search?q=강원&k=10"
bench_get "graph_schema"            "/graph/schema"
bench_get "graph_sample"            "/graph/sample?labels=Camp&limit=20"

# Heavy: /eta/batch over 10 sample ids — only useful when both sides have NCP.
if [ "$IDS_JSON" != "[]" ]; then
    BODY=$(printf '{"origin":"강남역","ids":%s,"max_minutes":300,"concurrency":4,"timeout_s":30}' "$IDS_JSON")
    bench_post "eta_batch_10ids" "/eta/batch" "$BODY"
else
    echo "(skip eta_batch — could not harvest sample camp ids)"
fi

echo "Done."
