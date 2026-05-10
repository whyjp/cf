// ListFacets use-case — 1:1 with the inline body of Python `api.facets`.
//
// Returns regions / concept_axes / concepts / themes for the FE filter UI.
// Concepts are bucketed by `is_axis` (axis vs long-tail).
package usecases

import (
	"context"

	"github.com/whyjp/cf/be-api/internal/ports"
)

// FacetsResult mirrors the Python `out` dict shape exactly. Field order
// follows Python: regions / concept_axes / concepts / themes.
type FacetsResult struct {
	Regions      []ports.RegionBucket  `json:"regions"`
	ConceptAxes  []ports.ConceptBucket `json:"concept_axes"`
	Concepts     []ports.ConceptBucket `json:"concepts"`
	Themes       []FacetTheme          `json:"themes"`
}

// FacetTheme mirrors the Python theme dict in /facets:
//
//	{"id": theme.id, "label": theme.label, "count": theme.member_count, "manual_label": theme.manual_label}
type FacetTheme struct {
	ID          string  `json:"id"`
	Label       string  `json:"label"`
	Count       int     `json:"count"`
	ManualLabel *string `json:"manual_label"`
}

// ListFacets wires FacetsReader + ThemeReader.
type ListFacets struct {
	facets ports.FacetsReader
	themes ports.ThemeReader
}

// NewListFacets constructs a ListFacets use-case.
func NewListFacets(f ports.FacetsReader, t ports.ThemeReader) *ListFacets {
	return &ListFacets{facets: f, themes: t}
}

// Execute matches the Python /facets handler. On error the Python handler
// catches and returns the partial dict with an X-Warning header — we surface
// the error and let the handler decide. (The byte-equal fixture tests run
// against a healthy DB so partial-failure mode is uncovered.)
func (uc *ListFacets) Execute(ctx context.Context) (*FacetsResult, error) {
	out := &FacetsResult{
		Regions:     []ports.RegionBucket{},
		ConceptAxes: []ports.ConceptBucket{},
		Concepts:    []ports.ConceptBucket{},
		Themes:      []FacetTheme{},
	}

	regions, err := uc.facets.Regions(ctx)
	if err != nil {
		return nil, err
	}
	if regions != nil {
		out.Regions = regions
	}

	concepts, err := uc.facets.ConceptsWithCounts(ctx)
	if err != nil {
		return nil, err
	}
	for _, c := range concepts {
		if c.IsAxis {
			out.ConceptAxes = append(out.ConceptAxes, c)
		} else {
			out.Concepts = append(out.Concepts, c)
		}
	}

	themes, err := uc.themes.All(ctx)
	if err != nil {
		return nil, err
	}
	for _, t := range themes {
		out.Themes = append(out.Themes, FacetTheme{
			ID: t.ID, Label: t.Label, Count: t.MemberCount, ManualLabel: t.ManualLabel,
		})
	}
	return out, nil
}
