// Package postgres wires the pgx pgxpool against the camfit Postgres
// schema. Adapters here implement ports defined in internal/ports.
package postgres

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

// NewPool creates a pgxpool.Pool from a Postgres DSN. Pool sizing is handled
// by pgx defaults (max 4) — D-7 perf bench will tune.
func NewPool(ctx context.Context, dsn string) (*pgxpool.Pool, error) {
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, err
	}
	return pgxpool.NewWithConfig(ctx, cfg)
}
