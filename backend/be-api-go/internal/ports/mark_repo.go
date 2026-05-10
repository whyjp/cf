package ports

import (
	"context"

	"github.com/whyjp/cf/be-api-go/internal/domain"
)

// MarkReader is the read-side port for `camp_marks`.
//
// Mirrors Python `MarkRepository.{for_camp, for_axis, all_axes}`.
type MarkReader interface {
	ForCamp(ctx context.Context, campID string) ([]*domain.Mark, error)
	ForAxis(ctx context.Context, axis string, minLevel *string, limit int) ([]*domain.Mark, error)
	AllAxes(ctx context.Context) ([]AxisCount, error)
}

// Note: AxisCount is defined in repo.go — the Python protocol places
// `MarkRepository.all_axes` next to it for the same reason (count rows are
// shared across the read/write split there).
