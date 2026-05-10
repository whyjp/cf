// EtaCacheRepo — pgx port of `cf_be_api.adapters.postgres.eta_cache_repo.PostgresEtaCacheRepo`.
//
// Schema (created by the existing Python migrations — D-5 does NOT issue DDL):
//
//	CREATE TABLE eta_cache (
//	  origin     text NOT NULL,
//	  dest       text NOT NULL,
//	  minutes    int,
//	  source     text,
//	  cached_at  timestamptz DEFAULT now(),
//	  PRIMARY KEY (origin, dest)
//	);
//
// Used by /eta + /eta/batch as a memoization layer (the road network is
// stable on the order of weeks; a 1-hour cache is overkill but cheap).
package postgres

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/whyjp/cf/be-api/internal/ports"
)

// EtaCacheRepo implements ports.EtaCache on top of pgxpool.
type EtaCacheRepo struct {
	pool *pgxpool.Pool
}

var _ ports.EtaCache = (*EtaCacheRepo)(nil)

// NewEtaCacheRepo constructs an EtaCacheRepo.
func NewEtaCacheRepo(pool *pgxpool.Pool) *EtaCacheRepo {
	return &EtaCacheRepo{pool: pool}
}

// Get returns (minutes, source, true, nil) on hit, (_, _, false, nil) on miss.
// A non-nil error means the query itself failed; rows-not-found is NOT an error.
func (r *EtaCacheRepo) Get(ctx context.Context, origin, dest string) (int, string, bool, error) {
	var minutes *int
	var source *string
	err := r.pool.QueryRow(ctx,
		"SELECT minutes, source FROM eta_cache WHERE origin=$1 AND dest=$2",
		origin, dest,
	).Scan(&minutes, &source)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return 0, "", false, nil
		}
		return 0, "", false, err
	}
	if minutes == nil {
		return 0, "", false, nil
	}
	src := ""
	if source != nil {
		src = *source
	}
	return *minutes, src, true, nil
}

// Put upserts (origin, dest) → (minutes, source). Pass minutes=nil to cache
// a known-failed lookup (negative caching) — handy for "no place name" miss.
func (r *EtaCacheRepo) Put(ctx context.Context, origin, dest string, minutes *int, source string) error {
	_, err := r.pool.Exec(ctx,
		`INSERT INTO eta_cache (origin, dest, minutes, source)
		 VALUES ($1, $2, $3, $4)
		 ON CONFLICT (origin, dest) DO UPDATE SET
		   minutes=EXCLUDED.minutes,
		   source=EXCLUDED.source,
		   cached_at=now()`,
		origin, dest, minutes, source,
	)
	return err
}

// Clear truncates the eta_cache table; returns the number of rows removed.
func (r *EtaCacheRepo) Clear(ctx context.Context) (int64, error) {
	tag, err := r.pool.Exec(ctx, "DELETE FROM eta_cache")
	if err != nil {
		return 0, err
	}
	return tag.RowsAffected(), nil
}
