// ConceptReader / theme / mark read-side ports.
//
// 1:1 with the Python `cf_be_api.ports.repo` Protocols (read paths only —
// write paths are out of D-4 scope and live in the same Protocols on the
// Python side; we'll add Go ports for them as needed in D-5+).
package ports

import (
	"context"

	"github.com/whyjp/cf/be-api-go/internal/domain"
)

// ConceptReader is the read-side port for the `concepts` table and the
// per-camp aggregation (camp_concept_aggregated → CampConcept).
//
// Mirrors Python `ConceptRepository.{all, for_camp, find_by_name}`.
type ConceptReader interface {
	All(ctx context.Context) ([]*domain.Concept, error)
	ForCamp(ctx context.Context, campID string) ([]*domain.CampConcept, error)
	FindByName(ctx context.Context, name string) (*domain.Concept, error)
}
