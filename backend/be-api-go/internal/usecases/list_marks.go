// ListMarks use-case — 1:1 with Python `api.list_marks` and `api.axis_camps`.
package usecases

import (
	"context"

	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// MarksResult mirrors the Python /marks return shape:
//
//	{"axes": [{"axis": ..., "count": ..., "top": [{"camp_id":..,"level":..,"score":..}]}]}
type MarksResult struct {
	Axes []AxisSummary `json:"axes"`
}

// AxisSummary is one element of `axes`.
type AxisSummary struct {
	Axis  string    `json:"axis"`
	Count int       `json:"count"`
	Top   []MarkTop `json:"top"`
}

// MarkTop mirrors the per-mark dict in `top`:
//
//	{"camp_id": m.camp_id, "level": m.level, "score": m.score}
type MarkTop struct {
	CampID string  `json:"camp_id"`
	Level  string  `json:"level"`
	Score  float64 `json:"score"`
}

// ListMarks wires MarkReader.
type ListMarks struct {
	marks ports.MarkReader
}

// NewListMarks constructs a ListMarks use-case.
func NewListMarks(m ports.MarkReader) *ListMarks {
	return &ListMarks{marks: m}
}

// Execute — Python:
//
//	axes = _container.mark_repo.all_axes()
//	out = []
//	for axis, count in axes:
//	    top = _container.mark_repo.for_axis(axis, min_level="exceptional", limit=3)
//	    out.append({"axis": axis, "count": count, "top": [...]})
//	return {"axes": out}
func (uc *ListMarks) Execute(ctx context.Context) (*MarksResult, error) {
	axes, err := uc.marks.AllAxes(ctx)
	if err != nil {
		return nil, err
	}
	res := &MarksResult{Axes: []AxisSummary{}}
	level := "exceptional"
	for _, ax := range axes {
		top, err := uc.marks.ForAxis(ctx, ax.Axis, &level, 3)
		if err != nil {
			return nil, err
		}
		topOut := make([]MarkTop, 0, len(top))
		for _, m := range top {
			topOut = append(topOut, MarkTop{CampID: m.CampID, Level: m.Level, Score: m.Score})
		}
		res.Axes = append(res.Axes, AxisSummary{
			Axis: ax.Axis, Count: ax.Count, Top: topOut,
		})
	}
	return res, nil
}

// AxisCamps — Python `api.axis_camps`:
//
//	marks = _container.mark_repo.for_axis(axis, min_level=min_level, limit=limit)
//	return [m.model_dump() for m in marks]
func (uc *ListMarks) AxisCamps(ctx context.Context, axis string, minLevel *string, limit int) ([]*domain.Mark, error) {
	out, err := uc.marks.ForAxis(ctx, axis, minLevel, limit)
	if err != nil {
		return nil, err
	}
	if out == nil {
		out = []*domain.Mark{}
	}
	return out, nil
}
