// Package falkor implements ports.GraphReader on top of falkordb-go.
//
// 1:1 with the Python `adapters.falkor.graph.FalkorGraph` adapter — same
// graph name default ("camfit"), same stateless connect-per-query pattern,
// same `RETURN 1` healthcheck.
package falkor

import (
	"context"
	"fmt"
	"net/url"
	"strconv"

	falkordb "github.com/FalkorDB/falkordb-go"
	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// Compile-time assertion: GraphRepo implements ports.GraphReader.
var _ ports.GraphReader = (*GraphRepo)(nil)

// GraphRepo holds a long-lived FalkorDB client and the target graph name.
type GraphRepo struct {
	db    *falkordb.FalkorDB
	graph string
}

// NewGraphRepo accepts either a redis URL ("redis://host:port") or a raw
// "host:port" string, mirroring the FALKORDB_URL env contract used by
// the Python adapter.
func NewGraphRepo(addr, graphName string) (*GraphRepo, error) {
	host, port, err := parseAddr(addr)
	if err != nil {
		return nil, err
	}
	db, err := falkordb.FalkorDBNew(&falkordb.ConnectionOption{
		Addr: fmt.Sprintf("%s:%d", host, port),
	})
	if err != nil {
		return nil, &domain.GraphUnavailable{Msg: err.Error()}
	}
	if graphName == "" {
		graphName = "camfit"
	}
	return &GraphRepo{db: db, graph: graphName}, nil
}

// Query runs a Cypher statement and converts the result set into row-dicts
// keyed by the column header. params == nil is fine — falkordb-go accepts an
// empty map.
//
// ctx is currently unused — falkordb-go's Query is synchronous and offers no
// cancellation hook (the underlying redigo client predates context.Context).
// We accept ctx for future-proofing and parity with other ports.
//
// falkordb-go v0.1.0 exposes results via an iterator — Next() / Record() —
// so we drain it into a slice of maps.
func (g *GraphRepo) Query(_ context.Context, cypher string, params map[string]any) ([]map[string]any, error) {
	if params == nil {
		params = map[string]any{}
	}
	graph := g.db.SelectGraph(g.graph)
	res, err := graph.Query(cypher, params, nil)
	if err != nil {
		return nil, &domain.GraphUnavailable{Msg: err.Error()}
	}
	if res == nil {
		return nil, nil
	}

	out := []map[string]any{}
	for res.Next() {
		rec := res.Record()
		if rec == nil {
			continue
		}
		keys := rec.Keys()
		values := rec.Values()
		row := make(map[string]any, len(keys))
		for i, k := range keys {
			if i < len(values) {
				row[k] = values[i]
			}
		}
		out = append(out, row)
	}
	return out, nil
}

// Reset wipes the target graph (defaults to g.graph). Used by D-6 admin
// endpoints. Mirrors `FalkorGraph.reset` — silent on empty/already-reset.
func (g *GraphRepo) Reset(_ context.Context, graphName string) error {
	if graphName == "" {
		graphName = g.graph
	}
	graph := g.db.SelectGraph(graphName)
	_, err := graph.Query("MATCH (n) DETACH DELETE n", map[string]any{}, nil)
	if err != nil {
		// Empty graph or already-reset is OK — same as Python adapter.
		return nil
	}
	return nil
}

// Healthcheck issues `RETURN 1`. False on any error.
func (g *GraphRepo) Healthcheck(_ context.Context) bool {
	graph := g.db.SelectGraph(g.graph)
	_, err := graph.Query("RETURN 1", map[string]any{}, nil)
	return err == nil
}

// parseAddr accepts redis:// URLs or raw host:port. Default port is 6379.
func parseAddr(addr string) (string, int, error) {
	if addr == "" {
		return "localhost", 6379, nil
	}
	if u, err := url.Parse(addr); err == nil && u.Scheme == "redis" {
		host := u.Hostname()
		if host == "" {
			host = "localhost"
		}
		port := 6379
		if p := u.Port(); p != "" {
			n, err := strconv.Atoi(p)
			if err != nil {
				return "", 0, fmt.Errorf("invalid port %q: %w", p, err)
			}
			port = n
		}
		return host, port, nil
	}
	// Raw "host:port"
	host, portStr, err := splitHostPort(addr)
	if err != nil {
		return addr, 6379, nil
	}
	n, err := strconv.Atoi(portStr)
	if err != nil {
		return host, 6379, nil
	}
	return host, n, nil
}

func splitHostPort(addr string) (string, string, error) {
	for i := len(addr) - 1; i >= 0; i-- {
		if addr[i] == ':' {
			return addr[:i], addr[i+1:], nil
		}
	}
	return "", "", fmt.Errorf("no port in %q", addr)
}
