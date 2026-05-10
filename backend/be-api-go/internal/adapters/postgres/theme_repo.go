// PostgresThemeRepo — pgx port of `adapters.postgres.theme_repo.PostgresThemeRepo`.
package postgres

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// ThemeRepo implements ports.ThemeReader on top of pgxpool.
type ThemeRepo struct {
	pool *pgxpool.Pool
}

// Compile-time assertion.
var _ ports.ThemeReader = (*ThemeRepo)(nil)

// NewThemeRepo constructs a ThemeRepo from an existing pgxpool.
func NewThemeRepo(pool *pgxpool.Pool) *ThemeRepo {
	return &ThemeRepo{pool: pool}
}

// All returns every theme — Python: `ORDER BY member_count DESC`.
//
// Centroid is NOT loaded here — the Python `.all()` does not select it and
// the /themes / /facets handlers don't expose it either. Themes returned by
// this method therefore have a nil `Centroid` slice; the JSON handlers
// project only id/label/member_count/manual_label.
func (r *ThemeRepo) All(ctx context.Context) ([]*domain.Theme, error) {
	rows, err := r.pool.Query(ctx,
		"SELECT id, label, member_count, manual_label FROM themes ORDER BY member_count DESC")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*domain.Theme
	for rows.Next() {
		var t domain.Theme
		if err := rows.Scan(&t.ID, &t.Label, &t.MemberCount, &t.ManualLabel); err != nil {
			return nil, err
		}
		out = append(out, &t)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return out, nil
}

// ForCamp returns the theme that the given camp belongs to (or nil if none).
//
// Python source:
//
//	SELECT t.id, t.label, t.member_count, t.manual_label
//	FROM themes t JOIN camp_themes ct ON t.id=ct.theme_id
//	WHERE ct.camp_id=%s
func (r *ThemeRepo) ForCamp(ctx context.Context, campID string) (*domain.Theme, error) {
	row := r.pool.QueryRow(ctx,
		`SELECT t.id, t.label, t.member_count, t.manual_label
		 FROM themes t JOIN camp_themes ct ON t.id=ct.theme_id
		 WHERE ct.camp_id=$1`, campID)
	var t domain.Theme
	if err := row.Scan(&t.ID, &t.Label, &t.MemberCount, &t.ManualLabel); err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &t, nil
}

// CampIDsForTheme returns up to `limit` camp IDs assigned to the theme.
//
// Python source (inlined in api.theme_camps):
//
//	SELECT camp_id FROM camp_themes WHERE theme_id=%s LIMIT %s
func (r *ThemeRepo) CampIDsForTheme(ctx context.Context, themeID string, limit int) ([]string, error) {
	rows, err := r.pool.Query(ctx,
		"SELECT camp_id FROM camp_themes WHERE theme_id=$1 LIMIT $2",
		themeID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		out = append(out, id)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return out, nil
}
