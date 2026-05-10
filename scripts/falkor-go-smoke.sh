#!/usr/bin/env bash
# SP-D D-1 — FalkorDB Go client maturity smoke test.
#
# Drives the D-2 falkor adapter strategy decision:
#   PASS = use github.com/FalkorDB/falkordb-go as the adapter.
#   FAIL = fall back to github.com/redis/go-redis/v9 + raw RESP `GRAPH.QUERY` commands.
#
# Requires:
#   * go (windows or linux)
#   * a reachable FalkorDB instance (default localhost:6379, override via FALKORDB_HOST)
#
# Outputs PASS/FAIL on stdout and exits non-zero on connection or query failure.
set -euo pipefail

cd "$(dirname "$0")/.."
SMOKE_DIR="smoke/falkor-go"
mkdir -p "$SMOKE_DIR"
cd "$SMOKE_DIR"

cat > go.mod <<'EOF'
module smoke/falkor-go

go 1.22

require github.com/FalkorDB/falkordb-go v0.1.0
EOF

cat > main.go <<'EOF'
package main

import (
	"fmt"
	"os"

	falkordb "github.com/FalkorDB/falkordb-go"
)

func main() {
	addr := os.Getenv("FALKORDB_HOST")
	if addr == "" {
		addr = "localhost:6379"
	}
	db, err := falkordb.FalkorDBNew(&falkordb.ConnectionOption{Addr: addr})
	if err != nil {
		fmt.Println("FAIL connect:", err)
		os.Exit(1)
	}
	graph := db.SelectGraph("camfit")
	// falkordb-go v0.1.0 Query signature: (query, params, options)
	res, err := graph.Query("MATCH (n) RETURN count(n) LIMIT 1", nil, nil)
	if err != nil {
		fmt.Println("FAIL query:", err)
		os.Exit(1)
	}
	fmt.Println("OK:", res)
}
EOF

go mod tidy 2>&1 | tail -3
go run main.go
