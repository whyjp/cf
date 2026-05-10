package ports

import "context"

// RegionBucket is one row of the regions[] facet — `(sido, sigungu, count)`.
type RegionBucket struct {
	Sido    string `json:"sido"`
	Sigungu string `json:"sigungu"`
	Count   int    `json:"count"`
}

// ConceptBucket is one row of the concept_axes[] / concepts[] facets.
//
// `count` = `SELECT count(*) FROM camp_concept_aggregated agg WHERE
// agg.concept_id = c.id AND agg.final_score > 0` — same matview-backed
// per-concept scorer as Python's facets handler.
type ConceptBucket struct {
	ID       string  `json:"id"`
	Name     string  `json:"name"`
	Category *string `json:"category"`
	IsAxis   bool    `json:"is_axis"`
	Count    int     `json:"count"`
}

// FacetsReader supplies the regions / concepts queries for /facets. Themes
// come from ThemeReader (already a port). Mirrors the Python facets handler
// SQL 1:1 — one method per query so the postgres layer stays the only place
// SQL strings live.
type FacetsReader interface {
	Regions(ctx context.Context) ([]RegionBucket, error)
	ConceptsWithCounts(ctx context.Context) ([]ConceptBucket, error)
}
