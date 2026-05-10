package ports

import (
	"context"

	"github.com/whyjp/cf/be-api/internal/domain"
)

// ThemeReader is the read-side port for the `themes` and `camp_themes`
// tables.
//
// Mirrors Python `ThemeRepository.{all, for_camp}` plus an extra
// `CampIDsForTheme` helper because Python /themes/{theme_id}/camps issues a
// raw SQL — we fold that into a port so the postgres layer stays the only
// place SQL strings live.
type ThemeReader interface {
	All(ctx context.Context) ([]*domain.Theme, error)
	ForCamp(ctx context.Context, campID string) (*domain.Theme, error)
	CampIDsForTheme(ctx context.Context, themeID string, limit int) ([]string, error)
}
