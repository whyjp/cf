// Package usecases hosts thin orchestration on top of ports — equivalent to
// `cf_be_api.usecases` in the Python source. Each use-case owns the wiring
// between a port query and any post-processing (e.g., camping_filter).
package usecases

import (
	"context"

	"github.com/whyjp/cf/be-api/internal/domain"
	"github.com/whyjp/cf/be-api/internal/ports"
)

// ListCamps implements the /sites read path:
//
//   - delegate to CampReader.ListCamps
//   - drop non-camping facilities (P6 — domain.IsCampingFacility)
//
// Mirrors the Python `api.sites` handler logic minus FastAPI plumbing.
type ListCamps struct {
	repo ports.CampReader
}

// NewListCamps constructs a ListCamps use-case.
func NewListCamps(repo ports.CampReader) *ListCamps {
	return &ListCamps{repo: repo}
}

// Execute fetches camps then applies the camping_filter predicate.
func (uc *ListCamps) Execute(ctx context.Context, opts ports.ListCampsOptions) ([]*domain.Camp, error) {
	camps, err := uc.repo.ListCamps(ctx, opts)
	if err != nil {
		return nil, err
	}
	out := make([]*domain.Camp, 0, len(camps))
	for _, c := range camps {
		if domain.IsCampingFacility(c) {
			out = append(out, c)
		}
	}
	return out, nil
}
