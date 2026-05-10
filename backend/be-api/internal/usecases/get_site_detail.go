// GetSiteDetail use-case — 1:1 with Python `usecases.get_site_detail.GetSiteDetail`.
//
// Returns the aggregated detail dict that the Python `/sites/{site_id}`
// handler returns: camp + reviews_top + reviews_total + concepts + theme.
package usecases

import (
	"context"

	"github.com/whyjp/cf/be-api/internal/domain"
	"github.com/whyjp/cf/be-api/internal/ports"
)

// SiteDetail mirrors the Python use-case's return dict shape exactly. JSON
// field order follows Python (camp / reviews_top / reviews_total / concepts /
// theme) — Pydantic preserves declaration order; Go does too via struct.
type SiteDetail struct {
	Camp         *domain.Camp        `json:"camp"`
	ReviewsTop   []*domain.Review    `json:"reviews_top"`
	ReviewsTotal int                 `json:"reviews_total"`
	Concepts     []SiteDetailConcept `json:"concepts"`
	Theme        *SiteDetailTheme    `json:"theme"`
}

// SiteDetailConcept mirrors the per-row dict in Python:
//
//	{"id": cc.concept_id, "score": cc.score}
type SiteDetailConcept struct {
	ID    string  `json:"id"`
	Score float64 `json:"score"`
}

// SiteDetailTheme mirrors the Python `theme` dict (omits centroid /
// manual_label since the use-case projects only id/label/member_count).
type SiteDetailTheme struct {
	ID          string `json:"id"`
	Label       string `json:"label"`
	MemberCount int    `json:"member_count"`
}

// GetSiteDetail wires CampReader + ReviewReader + ConceptReader + ThemeReader.
type GetSiteDetail struct {
	camps    ports.CampReader
	reviews  ports.ReviewReader
	concepts ports.ConceptReader
	themes   ports.ThemeReader
}

// NewGetSiteDetail constructs a GetSiteDetail use-case.
func NewGetSiteDetail(c ports.CampReader, r ports.ReviewReader,
	cr ports.ConceptReader, tr ports.ThemeReader) *GetSiteDetail {
	return &GetSiteDetail{camps: c, reviews: r, concepts: cr, themes: tr}
}

// Execute fetches the camp + its top reviews + concepts + theme.
//
// The handler is responsible for translating *domain.CampNotFound to 404 —
// we pass the underlying error through.
func (uc *GetSiteDetail) Execute(ctx context.Context, campID string, topReviewsN int) (*SiteDetail, error) {
	camp, err := uc.camps.Get(ctx, campID)
	if err != nil {
		return nil, err
	}
	reviews, err := uc.reviews.TopFor(ctx, campID, topReviewsN, "score")
	if err != nil {
		return nil, err
	}
	if reviews == nil {
		reviews = []*domain.Review{}
	}
	total, err := uc.reviews.TotalFor(ctx, campID)
	if err != nil {
		return nil, err
	}
	ccs, err := uc.concepts.ForCamp(ctx, campID)
	if err != nil {
		return nil, err
	}
	conceptOut := make([]SiteDetailConcept, 0, len(ccs))
	for _, cc := range ccs {
		conceptOut = append(conceptOut, SiteDetailConcept{ID: cc.ConceptID, Score: cc.Score})
	}
	theme, err := uc.themes.ForCamp(ctx, campID)
	if err != nil {
		return nil, err
	}
	var themeOut *SiteDetailTheme
	if theme != nil {
		themeOut = &SiteDetailTheme{
			ID: theme.ID, Label: theme.Label, MemberCount: theme.MemberCount,
		}
	}
	return &SiteDetail{
		Camp:         camp,
		ReviewsTop:   reviews,
		ReviewsTotal: total,
		Concepts:     conceptOut,
		Theme:        themeOut,
	}, nil
}
