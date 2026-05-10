// Package pgvector implements ports.VectorIndex on top of the pgvector
// PostgreSQL extension (`camp_embeddings` table). 1:1 with the Python
// `cf_be_api.adapters.pgvector.PgvectorIndex`:
//
//   - SearchByEmbedding ↔ knn (no filter_ids subset)
//   - GetEmbedding      ↔ get
//   - UpsertMany        ↔ upsert_many  (D-7: write-side for /admin/reembed)
//
// Schema (Python-side):
//
//	CREATE TABLE camp_embeddings (
//	  camp_id text PRIMARY KEY,
//	  vec     vector(768) NOT NULL,
//	  text_hash text,
//	  model_name text,
//	  created_at timestamptz default now()
//	);
//	CREATE INDEX idx_camp_embeddings_hnsw
//	  ON camp_embeddings USING hnsw (vec vector_cosine_ops);
//
// KNN uses the cosine-distance operator `<=>` (smaller = more similar) — same
// op the Python adapter uses, ensuring identical ordering.
package pgvector

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	pgv "github.com/pgvector/pgvector-go"

	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// Default model name written into camp_embeddings.model_name. Matches the
// Python default (`PgvectorIndex(__init__).model_name="ko-sroberta"`).
const defaultModelName = "ko-sroberta"

// Index implements ports.VectorIndex.
type Index struct {
	pool      *pgxpool.Pool
	modelName string
}

// Compile-time assertion: Index implements ports.VectorIndex.
var _ ports.VectorIndex = (*Index)(nil)

// Compile-time assertion: Index implements ports.VectorUpserter (write-side
// counterpart consumed by Reembed). Both port interfaces are satisfied by
// the same struct — same as the Python adapter where read + write hang off
// `PgvectorIndex`.
var _ ports.VectorUpserter = (*Index)(nil)

// NewIndex builds an Index over an existing pgxpool with the default model
// name ("ko-sroberta"). Use NewIndexWithModel to override.
func NewIndex(pool *pgxpool.Pool) *Index {
	return &Index{pool: pool, modelName: defaultModelName}
}

// NewIndexWithModel builds an Index that records modelName in upserted rows.
func NewIndexWithModel(pool *pgxpool.Pool, modelName string) *Index {
	if modelName == "" {
		modelName = defaultModelName
	}
	return &Index{pool: pool, modelName: modelName}
}

// SearchByEmbedding returns the top-k camp IDs ordered by cosine similarity
// (smallest cosine distance first). Uses pgvector `<=>` to match Python's
// `vec <=> %s` ordering verbatim.
func (i *Index) SearchByEmbedding(ctx context.Context, emb []float32, k int) ([]string, error) {
	if k <= 0 {
		return nil, nil
	}
	v := pgv.NewVector(emb)
	rows, err := i.pool.Query(ctx,
		`SELECT camp_id FROM camp_embeddings ORDER BY vec <=> $1 LIMIT $2`,
		v, k,
	)
	if err != nil {
		return nil, fmt.Errorf("pgvector knn: %w", err)
	}
	defer rows.Close()

	ids := make([]string, 0, k)
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, fmt.Errorf("scan camp_id: %w", err)
		}
		ids = append(ids, id)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return ids, nil
}

// UpsertMany writes (camp_id, vec, text_hash, model_name) rows in a single
// pgx batch. 1:1 with Python `PgvectorIndex.upsert_many` —
//
//	INSERT INTO camp_embeddings (camp_id, vec, text_hash, model_name)
//	  VALUES ($1, $2, $3, $4)
//	  ON CONFLICT (camp_id) DO UPDATE SET
//	    vec = EXCLUDED.vec,
//	    text_hash = EXCLUDED.text_hash,
//	    model_name = EXCLUDED.model_name,
//	    created_at = now()
//
// Returns the count of items processed (matches Python `n` return). Empty
// input returns (0, nil) without touching the pool. Errors short-circuit the
// batch and surface unwrapped.
func (i *Index) UpsertMany(ctx context.Context, items []ports.VectorItem) (int, error) {
	if len(items) == 0 {
		return 0, nil
	}
	batch := &pgx.Batch{}
	for _, it := range items {
		batch.Queue(
			`INSERT INTO camp_embeddings (camp_id, vec, text_hash, model_name)
			 VALUES ($1, $2, $3, $4)
			 ON CONFLICT (camp_id) DO UPDATE SET
			   vec = EXCLUDED.vec,
			   text_hash = EXCLUDED.text_hash,
			   model_name = EXCLUDED.model_name,
			   created_at = now()`,
			it.CampID, pgv.NewVector(it.Vec), it.TextHash, i.modelName,
		)
	}
	br := i.pool.SendBatch(ctx, batch)
	defer br.Close()
	n := 0
	for range items {
		if _, err := br.Exec(); err != nil {
			return n, fmt.Errorf("pgvector upsert: %w", err)
		}
		n++
	}
	return n, nil
}

// GetEmbedding returns the stored 768-d vector for an item, or
// (nil, pgx.ErrNoRows) if no row exists. Equivalent to Python's
// `vector.get(site_id)` returning None.
func (i *Index) GetEmbedding(ctx context.Context, itemID string) ([]float32, error) {
	var v pgv.Vector
	err := i.pool.QueryRow(ctx,
		`SELECT vec FROM camp_embeddings WHERE camp_id=$1`, itemID,
	).Scan(&v)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, pgx.ErrNoRows
		}
		return nil, fmt.Errorf("pgvector get: %w", err)
	}
	return v.Slice(), nil
}
