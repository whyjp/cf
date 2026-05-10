// PostgresConceptRepo — pgx port of `adapters.postgres.concept_repo.PostgresConceptRepo`.
//
// SQL is a 1:1 translation of the Python source (only the read paths needed
// by D-4 are implemented; write paths land in D-5 when ingest moves to Go).
package postgres

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// ConceptRepo implements ports.ConceptReader on top of pgxpool.
type ConceptRepo struct {
	pool *pgxpool.Pool
}

// Compile-time assertion: ConceptRepo implements ports.ConceptReader.
var _ ports.ConceptReader = (*ConceptRepo)(nil)

// NewConceptRepo constructs a ConceptRepo from an existing pgxpool.
func NewConceptRepo(pool *pgxpool.Pool) *ConceptRepo {
	return &ConceptRepo{pool: pool}
}

// All returns every row of `concepts`.
//
// Python source: `SELECT id, name, source, category, description, is_axis FROM concepts`.
// Note: Python `.all()` does NOT specify ORDER BY — Postgres returns physical
// row order, which (after the matview joins/inserts of build_vocabulary)
// happens to be stable in practice. We match by NOT adding any ORDER BY.
func (r *ConceptRepo) All(ctx context.Context) ([]*domain.Concept, error) {
	rows, err := r.pool.Query(ctx,
		"SELECT id, name, source, category, description, is_axis FROM concepts")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*domain.Concept
	for rows.Next() {
		c, err := scanConcept(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, c)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return out, nil
}

// ForCamp returns the aggregated concept rows for one camp.
//
// Python source: `SELECT camp_id, concept_id, final_score FROM
// camp_concept_aggregated WHERE camp_id=%s`.
func (r *ConceptRepo) ForCamp(ctx context.Context, campID string) ([]*domain.CampConcept, error) {
	rows, err := r.pool.Query(ctx,
		"SELECT camp_id, concept_id, final_score FROM camp_concept_aggregated WHERE camp_id=$1",
		campID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*domain.CampConcept
	for rows.Next() {
		var cc domain.CampConcept
		if err := rows.Scan(&cc.CampID, &cc.ConceptID, &cc.Score); err != nil {
			return nil, err
		}
		out = append(out, &cc)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return out, nil
}

// FindByName mirrors Python `find_by_name`. Returns nil (no error) when no row.
func (r *ConceptRepo) FindByName(ctx context.Context, name string) (*domain.Concept, error) {
	row := r.pool.QueryRow(ctx,
		"SELECT id, name, source, category, description, is_axis FROM concepts WHERE name=$1",
		name)
	c, err := scanConcept(row)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return c, nil
}

// concept scanner shared by All / FindByName.
func scanConcept(row pgx.Row) (*domain.Concept, error) {
	var c domain.Concept
	if err := row.Scan(&c.ID, &c.Name, &c.Source, &c.Category, &c.Description, &c.IsAxis); err != nil {
		return nil, err
	}
	// SeedTerm is not loaded by the Python `.all()` either — Pydantic defaults
	// it to None and `model_dump()` emits "seed_term": null. Same here.
	return &c, nil
}
