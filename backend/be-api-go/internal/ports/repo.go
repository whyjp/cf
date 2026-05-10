// Package ports defines hexagonal-architecture interfaces — adapters in
// internal/adapters/ implement them, use-cases in internal/usecases/ consume
// them. 1:1 with the Python `cf_be_api.ports` package.
package ports

import (
	"context"

	"github.com/whyjp/cf/be-api-go/internal/domain"
)

// ListCampsOptions mirrors the keyword arguments of
// `CampReader.list_filtered` in Python.
//
// Pointer fields = Python `Optional[T]` (None vs unset distinction). For
// slices we use nil to mean "not specified"; len(0) is currently treated the
// same as nil by the Postgres adapter.
type ListCampsOptions struct {
	Sido        *string
	Sigungu     *string
	Concept     []string  // AND semantics
	ConceptsAny []string  // OR semantics
	MinScore    *float64
	MaxScore    *float64
	Bbox        *Bbox
	IDs         []string
	Limit       int       // Default 10000 (P5 cap lifted from 2000)
}

// Bbox is (lon1, lat1, lon2, lat2) — the same tuple shape Python uses.
type Bbox struct {
	Lon1, Lat1, Lon2, Lat2 float64
}

// CampReader is the read-side port for camp records.
type CampReader interface {
	Get(ctx context.Context, campID string) (*domain.Camp, error)
	ListCamps(ctx context.Context, opts ListCampsOptions) ([]*domain.Camp, error)
	Count(ctx context.Context) (int, error)
}

// CampWriter — write-side (used by ingest, not by /sites). Filled out in
// later sprints (D-5+) when ingest moves to Go.
type CampWriter interface {
	UpsertMany(ctx context.Context, camps []*domain.Camp) (int, error)
	SetGeo(ctx context.Context, campID string, lat, lon float64) error
	Delete(ctx context.Context, campID string) (bool, error)
}

// ReviewReader — D-4+ semantic detail endpoints.
type ReviewReader interface {
	TopFor(ctx context.Context, campID string, n int, sort string) ([]*domain.Review, error)
	TotalFor(ctx context.Context, campID string) (int, error)
}

// ConceptRepository — D-3+ concept assignment.
type ConceptRepository interface {
	UpsertConcept(ctx context.Context, c *domain.Concept) error
	Assign(ctx context.Context, campID, conceptID string, score float64, evidence *string) error
	ForCamp(ctx context.Context, campID string) ([]*domain.CampConcept, error)
	All(ctx context.Context) ([]*domain.Concept, error)
	FindByName(ctx context.Context, name string) (*domain.Concept, error)
	DeleteByID(ctx context.Context, conceptID string) error
}

// ThemeRepository — D-6 theme/clustering endpoints.
type ThemeRepository interface {
	ReplaceAll(ctx context.Context, themes []*domain.Theme) error
	Assign(ctx context.Context, campID, themeID string) error
	ForCamp(ctx context.Context, campID string) (*domain.Theme, error)
	All(ctx context.Context) ([]*domain.Theme, error)
}

// MarkRepository — D-4+ mark axis endpoints.
type MarkRepository interface {
	ReplaceForCamp(ctx context.Context, campID string, marks []*domain.Mark) (int, error)
	ForCamp(ctx context.Context, campID string) ([]*domain.Mark, error)
	ForAxis(ctx context.Context, axis string, minLevel *string, limit int) ([]*domain.Mark, error)
	AllAxes(ctx context.Context) ([]AxisCount, error)
}

// AxisCount is `(axis_name, count)` ordered by count desc — matches Python's
// `MarkRepository.all_axes()` return shape.
type AxisCount struct {
	Axis  string
	Count int
}
