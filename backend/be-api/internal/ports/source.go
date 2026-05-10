package ports

import (
	"context"

	"github.com/whyjp/cf/be-api/internal/domain"
)

// SourceReader is the iteration-style data-source port. 1:1 with Python
// `ports.source.DataSource`, using channels instead of generators.
//
// The `errs` channel is single-buffered so the producer can post a final
// error without the consumer racing on close. The consumer should always
// drain `out` *and* check `errs` after the channel is closed.
type SourceReader interface {
	Name() string
	IterSummaries(ctx context.Context) (<-chan *domain.Camp, <-chan error)
	GetDetail(ctx context.Context, campID string) (*domain.Camp, error)
	IterReviews(ctx context.Context, campID string, sort string) (<-chan *domain.Review, <-chan error)
	IterFilters(ctx context.Context) (<-chan FilterEntry, <-chan error)
}

// FilterEntry mirrors the Python tuple `(id, name, kind, raw_json)`.
type FilterEntry struct {
	ID   string
	Name string
	Kind string
	Raw  map[string]any
}
