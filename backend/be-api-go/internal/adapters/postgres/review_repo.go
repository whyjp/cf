// PostgresReviewRepo — pgx port of the read-side methods of
// `adapters.postgres.review_repo.PostgresReviewReader`.
package postgres

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// ReviewRepo implements ports.ReviewReader on top of pgxpool.
type ReviewRepo struct {
	pool *pgxpool.Pool
}

// Compile-time assertion.
var _ ports.ReviewReader = (*ReviewRepo)(nil)

// NewReviewRepo constructs a ReviewRepo from an existing pgxpool.
func NewReviewRepo(pool *pgxpool.Pool) *ReviewRepo {
	return &ReviewRepo{pool: pool}
}

// TopFor returns the top-N reviews for a camp.
//
// Python source: `ORDER BY score DESC NULLS LAST` for sort=score (default),
// `ORDER BY review_timestamp DESC` for sort=recent. medias[] is intentionally
// NOT loaded here — the Python `.top_for` doesn't load it either (review_medias
// is a separate table joined on demand by the writer/iter paths). model_dump
// emits `"medias": []` for the empty default — same as Go.
func (r *ReviewRepo) TopFor(ctx context.Context, campID string, n int, sort string) ([]*domain.Review, error) {
	order := "score DESC NULLS LAST"
	if sort == "recent" {
		order = "review_timestamp DESC"
	}
	sql := `SELECT id, camp_id, user_nick, season, user_type, num_of_days,
	        score, text, is_clean, is_kind, is_manner, is_convenient, review_timestamp
	        FROM reviews WHERE camp_id=$1 ORDER BY ` + order + ` LIMIT $2`
	rows, err := r.pool.Query(ctx, sql, campID, n)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*domain.Review
	for rows.Next() {
		rev := &domain.Review{Medias: []string{}}
		if err := rows.Scan(
			&rev.ID, &rev.CampID, &rev.UserNick, &rev.Season, &rev.UserType, &rev.NumOfDays,
			&rev.Score, &rev.Text, &rev.IsClean, &rev.IsKind, &rev.IsManner, &rev.IsConvenient,
			&rev.ReviewTimestamp,
		); err != nil {
			return nil, err
		}
		out = append(out, rev)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return out, nil
}

// TotalFor returns the row count of reviews for a camp.
//
// Python source: `SELECT count(*) FROM reviews WHERE camp_id=%s`.
func (r *ReviewRepo) TotalFor(ctx context.Context, campID string) (int, error) {
	var n int
	if err := r.pool.QueryRow(ctx,
		"SELECT count(*) FROM reviews WHERE camp_id=$1", campID).Scan(&n); err != nil {
		return 0, err
	}
	return n, nil
}
