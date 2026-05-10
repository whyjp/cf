// PostgresMarkRepo — pgx port of `adapters.postgres.mark_repo.PostgresMarkRepo`.
package postgres

import (
	"context"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/whyjp/cf/be-api/internal/domain"
	"github.com/whyjp/cf/be-api/internal/ports"
)

// markLevelsOrder mirrors `_LEVELS_ORDER` in Python — the strict ordering
// used to expand a `min_level` filter into the IN(...) set ("notable" =>
// {notable, exceptional}, etc.).
var markLevelsOrder = []string{"bib", "recommended", "notable", "exceptional"}

// MarkRepo implements ports.MarkReader on top of pgxpool.
type MarkRepo struct {
	pool *pgxpool.Pool
}

// Compile-time assertion.
var _ ports.MarkReader = (*MarkRepo)(nil)

// NewMarkRepo constructs a MarkRepo from an existing pgxpool.
func NewMarkRepo(pool *pgxpool.Pool) *MarkRepo {
	return &MarkRepo{pool: pool}
}

// ForCamp — Python: `... WHERE camp_id=%s ORDER BY axis`.
func (r *MarkRepo) ForCamp(ctx context.Context, campID string) ([]*domain.Mark, error) {
	rows, err := r.pool.Query(ctx,
		`SELECT camp_id, axis, level, score, evidence
		 FROM camp_marks WHERE camp_id=$1
		 ORDER BY axis`, campID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanMarks(rows)
}

// ForAxis — Python:
//
//	if min_level: ... WHERE axis=%s AND level IN (...) ORDER BY score DESC LIMIT %s
//	else:         ... WHERE axis=%s ORDER BY score DESC LIMIT %s
//
// Python raises ValueError on an unknown level — we surface it as a Go
// `fmt.Errorf` which the handler maps to a 4xx (currently 500; the Python
// handler doesn't catch it either, FastAPI returns 500). Matching behaviour.
func (r *MarkRepo) ForAxis(ctx context.Context, axis string, minLevel *string, limit int) ([]*domain.Mark, error) {
	if minLevel != nil && *minLevel != "" {
		idx := -1
		for i, l := range markLevelsOrder {
			if l == *minLevel {
				idx = i
				break
			}
		}
		if idx == -1 {
			return nil, fmt.Errorf("invalid level: %s", *minLevel)
		}
		allowed := markLevelsOrder[idx:]
		// Build `level IN ($2, $3, ...)` from the slice; pgx uses $-positional
		// placeholders rather than the comma-expanded `%s, %s` Python pattern.
		holders := make([]string, len(allowed))
		args := make([]any, 0, len(allowed)+2)
		args = append(args, axis)
		for i, l := range allowed {
			holders[i] = fmt.Sprintf("$%d", i+2)
			args = append(args, l)
		}
		args = append(args, limit)
		sql := fmt.Sprintf(
			`SELECT camp_id, axis, level, score, evidence
			 FROM camp_marks
			 WHERE axis=$1 AND level IN (%s)
			 ORDER BY score DESC LIMIT $%d`,
			strings.Join(holders, ","), len(allowed)+2)
		rows, err := r.pool.Query(ctx, sql, args...)
		if err != nil {
			return nil, err
		}
		defer rows.Close()
		return scanMarks(rows)
	}
	rows, err := r.pool.Query(ctx,
		`SELECT camp_id, axis, level, score, evidence
		 FROM camp_marks WHERE axis=$1
		 ORDER BY score DESC LIMIT $2`, axis, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanMarks(rows)
}

// AllAxes — Python: `SELECT axis, count(*) FROM camp_marks GROUP BY axis ORDER BY count(*) DESC`.
func (r *MarkRepo) AllAxes(ctx context.Context) ([]ports.AxisCount, error) {
	rows, err := r.pool.Query(ctx,
		"SELECT axis, count(*) FROM camp_marks GROUP BY axis ORDER BY count(*) DESC")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []ports.AxisCount
	for rows.Next() {
		var a string
		var n int
		if err := rows.Scan(&a, &n); err != nil {
			return nil, err
		}
		out = append(out, ports.AxisCount{Axis: a, Count: n})
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return out, nil
}

// scanMarks drains a Rows of camp_marks.
func scanMarks(rows interface {
	Next() bool
	Scan(dest ...any) error
	Err() error
}) ([]*domain.Mark, error) {
	var out []*domain.Mark
	for rows.Next() {
		var m domain.Mark
		if err := rows.Scan(&m.CampID, &m.Axis, &m.Level, &m.Score, &m.Evidence); err != nil {
			return nil, err
		}
		out = append(out, &m)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return out, nil
}
