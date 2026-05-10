// PostgresFacetsRepo — pgx port of the inline SQL inside Python `api.facets`.
//
// /facets calls `_container._pg.conn().cursor().execute(...)` directly with
// two queries:
//   1. regions buckets (sido, sigungu, count) where sido IS NOT NULL
//   2. concepts with per-concept matview-derived counts (camp_concept_aggregated)
//
// We fold those into a port so the postgres layer stays the only place SQL
// lives.
package postgres

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/whyjp/cf/be-api/internal/ports"
)

// FacetsRepo implements ports.FacetsReader on top of pgxpool.
type FacetsRepo struct {
	pool *pgxpool.Pool
}

// Compile-time assertion.
var _ ports.FacetsReader = (*FacetsRepo)(nil)

// NewFacetsRepo constructs a FacetsRepo.
func NewFacetsRepo(pool *pgxpool.Pool) *FacetsRepo {
	return &FacetsRepo{pool: pool}
}

// Regions — Python source:
//
//	SELECT sido, sigungu, count(*) FROM camps
//	WHERE sido IS NOT NULL GROUP BY sido, sigungu ORDER BY count(*) DESC
func (r *FacetsRepo) Regions(ctx context.Context) ([]ports.RegionBucket, error) {
	rows, err := r.pool.Query(ctx,
		`SELECT sido, sigungu, count(*) FROM camps
		 WHERE sido IS NOT NULL GROUP BY sido, sigungu ORDER BY count(*) DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []ports.RegionBucket
	for rows.Next() {
		var b ports.RegionBucket
		if err := rows.Scan(&b.Sido, &b.Sigungu, &b.Count); err != nil {
			return nil, err
		}
		out = append(out, b)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return out, nil
}

// ConceptsWithCounts — Python source:
//
//	SELECT c.id, c.name, c.category, c.is_axis,
//	       (SELECT count(*) FROM camp_concept_aggregated agg
//	        WHERE agg.concept_id = c.id AND agg.final_score > 0) AS n
//	FROM concepts c
//	ORDER BY n DESC NULLS LAST
//
// Note Python casts `int(r[4] or 0)` — the subquery never returns NULL
// (count(*) is always 0 for missing rows), but we mirror the defensive cast.
func (r *FacetsRepo) ConceptsWithCounts(ctx context.Context) ([]ports.ConceptBucket, error) {
	rows, err := r.pool.Query(ctx,
		`SELECT c.id, c.name, c.category, c.is_axis,
		        (SELECT count(*) FROM camp_concept_aggregated agg
		         WHERE agg.concept_id = c.id AND agg.final_score > 0) AS n
		 FROM concepts c
		 ORDER BY n DESC NULLS LAST`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []ports.ConceptBucket
	for rows.Next() {
		var b ports.ConceptBucket
		var n *int64
		if err := rows.Scan(&b.ID, &b.Name, &b.Category, &b.IsAxis, &n); err != nil {
			return nil, err
		}
		if n != nil {
			b.Count = int(*n)
		}
		out = append(out, b)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return out, nil
}
