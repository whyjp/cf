// SemanticSearch use-case — 1:1 with Python `cf_be_api.usecases.semantic_search`.
//
// Two flows:
//
//  1. Search(q, k):  q → embedder.Encode → vector.SearchByEmbedding → camps (KNN
//     order preserved, then P6 camping_filter applied — same as Python /sites/
//     search handler).
//  2. Similar(siteID, k): vector.GetEmbedding(siteID) → vector.SearchByEmbedding
//     (k+1 to drop self) → camps. Python uses the camp's stored embedding
//     directly rather than re-embedding name+description; we match that.
//
// Camp-not-found is surfaced as ErrNoEmbedding so the handler can return 404
// (matches Python `HTTPException(404, "no embedding for camp ...")`).
package usecases

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"

	"github.com/whyjp/cf/be-api/internal/domain"
	"github.com/whyjp/cf/be-api/internal/ports"
)

// ErrNoEmbedding signals that VectorIndex.GetEmbedding returned no row for
// the requested camp ID. Surfaced by Similar.
var ErrNoEmbedding = errors.New("no embedding for camp")

// SemanticSearch wires Embedder + VectorIndex + CampReader.
type SemanticSearch struct {
	embed  ports.Embedder
	vector ports.VectorIndex
	repo   ports.CampReader
}

// NewSemanticSearch constructs a SemanticSearch use-case.
func NewSemanticSearch(e ports.Embedder, v ports.VectorIndex, r ports.CampReader) *SemanticSearch {
	return &SemanticSearch{embed: e, vector: v, repo: r}
}

// Search executes the q → KNN → camps pipeline with P6 camping_filter applied.
// KNN order is preserved in the returned slice (camps are re-sorted to match
// the order of IDs returned by VectorIndex.SearchByEmbedding).
func (s *SemanticSearch) Search(ctx context.Context, q string, k int) ([]*domain.Camp, error) {
	if k <= 0 {
		return nil, nil
	}
	emb, err := s.embed.Encode(ctx, q)
	if err != nil {
		return nil, err
	}
	ids, err := s.vector.SearchByEmbedding(ctx, emb, k)
	if err != nil {
		return nil, err
	}
	return s.hydrateOrdered(ctx, ids), nil
}

// Similar returns up to k camps closest to siteID (excluding siteID itself),
// using the camp's own indexed embedding (not a re-embedding of its name).
// Returns ErrNoEmbedding wrapped if siteID has no row in camp_embeddings.
func (s *SemanticSearch) Similar(ctx context.Context, siteID string, k int) ([]*domain.Camp, error) {
	if k <= 0 {
		return nil, nil
	}
	vec, err := s.vector.GetEmbedding(ctx, siteID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNoEmbedding
		}
		return nil, err
	}
	// +1 to allow dropping self; Python uses k+1 for the same reason.
	ids, err := s.vector.SearchByEmbedding(ctx, vec, k+1)
	if err != nil {
		return nil, err
	}
	others := make([]string, 0, k)
	for _, id := range ids {
		if id == siteID {
			continue
		}
		others = append(others, id)
		if len(others) == k {
			break
		}
	}
	return s.hydrateOrdered(ctx, others), nil
}

// hydrateOrdered fetches each camp by ID, preserving the input order and
// applying P6 camping_filter. Best-effort: missing camps and lookup errors
// are silently dropped (Python behaves the same — the ordered map is rebuilt
// from list_filtered output and only ids that match survive).
func (s *SemanticSearch) hydrateOrdered(ctx context.Context, ids []string) []*domain.Camp {
	out := make([]*domain.Camp, 0, len(ids))
	for _, id := range ids {
		c, err := s.repo.Get(ctx, id)
		if err != nil || c == nil {
			continue
		}
		if !domain.IsCampingFacility(c) {
			continue
		}
		out = append(out, c)
	}
	return out
}
