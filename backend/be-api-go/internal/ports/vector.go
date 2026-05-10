// VectorIndex port — k-nearest-neighbour over stored embeddings.
//
// 1:1 with the Python `cf_be_api.ports.vector.VectorIndex` (KNN-only subset
// used by `/sites/search` and `/sites/{id}/similar`). Adapter implementation
// lives in `internal/adapters/pgvector/`.
package ports

import "context"

// VectorIndex provides KNN over stored item embeddings (ID-keyed).
//
// SearchByEmbedding takes an already-encoded query vector and returns the
// top-k IDs ordered by similarity. GetEmbedding loads a stored embedding by
// item ID — used for "similar to this site" flows where we re-use a camp's
// own indexed vector.
type VectorIndex interface {
	SearchByEmbedding(ctx context.Context, emb []float32, k int) ([]string, error)
	GetEmbedding(ctx context.Context, itemID string) ([]float32, error)
}
