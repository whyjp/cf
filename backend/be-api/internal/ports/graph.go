package ports

import "context"

// GraphReader mirrors the Python `ports.graph.GraphStore` Protocol — a
// minimal Cypher-via-FalkorDB facade for D-6 admin/graph endpoints.
//
// The result shape `[]map[string]any` is more idiomatic in Go than the
// Python `list[list[Any]]` because FalkorDB returns named columns; the
// adapter converts `(headers, rows)` into row-dicts so handlers can
// `result["camp"]` rather than juggling indices.
type GraphReader interface {
	Query(ctx context.Context, cypher string, params map[string]any) ([]map[string]any, error)
	Reset(ctx context.Context, graphName string) error
	Healthcheck(ctx context.Context) bool
}
