// ListThemes use-case — 1:1 with Python `api.themes` and `api.theme_camps`.
package usecases

import (
	"context"

	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// ThemeRow mirrors the projection in Python `api.themes`:
//
//	{"id": t.id, "label": t.label, "count": t.member_count, "manual_label": t.manual_label}
type ThemeRow struct {
	ID          string  `json:"id"`
	Label       string  `json:"label"`
	Count       int     `json:"count"`
	ManualLabel *string `json:"manual_label"`
}

// ListThemes wires ThemeReader + CampReader.
type ListThemes struct {
	themes ports.ThemeReader
	camps  ports.CampReader
}

// NewListThemes constructs a ListThemes use-case.
func NewListThemes(t ports.ThemeReader, c ports.CampReader) *ListThemes {
	return &ListThemes{themes: t, camps: c}
}

// All — projects to ThemeRow.
func (uc *ListThemes) All(ctx context.Context) ([]ThemeRow, error) {
	rows, err := uc.themes.All(ctx)
	if err != nil {
		return nil, err
	}
	out := make([]ThemeRow, 0, len(rows))
	for _, t := range rows {
		out = append(out, ThemeRow{
			ID: t.ID, Label: t.Label, Count: t.MemberCount, ManualLabel: t.ManualLabel,
		})
	}
	return out, nil
}

// CampsForTheme — Python `api.theme_camps`:
//
//	with _container._pg.conn() as c, c.cursor() as cur:
//	    cur.execute("SELECT camp_id FROM camp_themes WHERE theme_id=%s LIMIT %s", (theme_id, limit))
//	    ids = [r[0] for r in cur.fetchall()]
//	if not ids:
//	    return []
//	rows = _container.camps_read.list_filtered(ids=ids, limit=limit)
//	return [c.model_dump() for c in rows]
//
// Same NOT-camping_filter behaviour as concept_camps — Python doesn't filter.
func (uc *ListThemes) CampsForTheme(ctx context.Context, themeID string, limit int) ([]*domain.Camp, error) {
	ids, err := uc.themes.CampIDsForTheme(ctx, themeID, limit)
	if err != nil {
		return nil, err
	}
	if len(ids) == 0 {
		return []*domain.Camp{}, nil
	}
	rows, err := uc.camps.ListCamps(ctx, ports.ListCampsOptions{
		IDs:   ids,
		Limit: limit,
	})
	if err != nil {
		return nil, err
	}
	if rows == nil {
		rows = []*domain.Camp{}
	}
	return rows, nil
}
