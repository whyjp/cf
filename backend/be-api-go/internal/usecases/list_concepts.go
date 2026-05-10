// ListConcepts use-case — 1:1 with Python `api.concepts` and `api.concept_camps`.
package usecases

import (
	"context"

	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// ListConcepts wires ConceptReader + CampReader (the latter for ConceptCamps).
type ListConcepts struct {
	concepts ports.ConceptReader
	camps    ports.CampReader
}

// NewListConcepts constructs a ListConcepts use-case.
func NewListConcepts(c ports.ConceptReader, camps ports.CampReader) *ListConcepts {
	return &ListConcepts{concepts: c, camps: camps}
}

// All — Python: `[c.model_dump() for c in _container.concept_repo.all()]`.
func (uc *ListConcepts) All(ctx context.Context) ([]*domain.Concept, error) {
	out, err := uc.concepts.All(ctx)
	if err != nil {
		return nil, err
	}
	if out == nil {
		out = []*domain.Concept{}
	}
	return out, nil
}

// CampsForConcept — Python `api.concept_camps`:
//
//	rows = _container.camps_read.list_filtered(
//	    concept=[name], min_score=min_score, limit=limit,
//	)
//	return [c.model_dump() for c in rows]
//
// Note Python does NOT apply camping_filter here — only /sites and
// /sites/search /similar do. We match that exactly.
func (uc *ListConcepts) CampsForConcept(ctx context.Context, name string, minScore float64, limit int) ([]*domain.Camp, error) {
	ms := minScore
	rows, err := uc.camps.ListCamps(ctx, ports.ListCampsOptions{
		Concept:  []string{name},
		MinScore: &ms,
		Limit:    limit,
	})
	if err != nil {
		return nil, err
	}
	if rows == nil {
		rows = []*domain.Camp{}
	}
	return rows, nil
}
