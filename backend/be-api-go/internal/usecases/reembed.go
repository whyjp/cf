// Reembed use-case — 1:1 with Python `usecases.build_embeddings.BuildEmbeddings`.
//
// Reads every camp + their top-N reviews, builds the canonical "embed text"
// (camp name / region / brief / location_brief / description / hashtags +
// review excerpts), encodes via the configured Embedder, and upserts each
// (camp_id, vector, text_hash) into the VectorIndex.
//
// Idempotent: same camp + unchanged text_hash → re-upsert with a fresh
// created_at (matches Python; no skip-if-unchanged optimisation in v1).
//
// Note on dependencies: this use-case introduces a `VectorUpserter` interface
// here (rather than extending ports.VectorIndex) because the read-side
// `VectorIndex` is consumed by /sites/search and we want to keep that port
// stable across D-3 → D-6. A separate write-side adapter or a typed assert
// in the wiring layer can satisfy `VectorUpserter` once the `camp_embeddings`
// upsert SQL lands.
package usecases

import (
	"context"
	"crypto/sha1"
	"encoding/hex"
	"strings"

	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// VectorUpserter is the write-side complement of ports.VectorIndex used by
// Reembed. UpsertMany returns the number of rows affected (Python parity).
type VectorUpserter interface {
	UpsertMany(ctx context.Context, items []VectorItem) (int, error)
}

// VectorItem is a single row in the camp_embeddings table — same fields as
// the Python `(camp_id, vec, text_hash)` tuple.
type VectorItem struct {
	CampID   string
	Vec      []float32
	TextHash string
}

// Reembed wires CampReader + ReviewReader + Embedder + VectorUpserter.
type Reembed struct {
	camps     ports.CampReader
	reviews   ports.ReviewReader
	embedder  ports.Embedder
	vectors   VectorUpserter
	batchSize int
}

// NewReembed constructs a Reembed use-case. batchSize defaults to 32 (matches
// Python).
func NewReembed(
	camps ports.CampReader,
	reviews ports.ReviewReader,
	embedder ports.Embedder,
	vectors VectorUpserter,
) *Reembed {
	return &Reembed{
		camps: camps, reviews: reviews, embedder: embedder, vectors: vectors,
		batchSize: 32,
	}
}

// Execute returns the count of camps embedded (matches Python's int return).
func (uc *Reembed) Execute(ctx context.Context) (int, error) {
	camps, err := uc.camps.ListCamps(ctx, ports.ListCampsOptions{Limit: 100000})
	if err != nil {
		return 0, err
	}
	if len(camps) == 0 {
		return 0, nil
	}

	items := make([]VectorItem, 0, len(camps))
	for _, camp := range camps {
		top, err := uc.reviews.TopFor(ctx, camp.ID, 5, "")
		if err != nil {
			return 0, err
		}
		text := buildEmbedText(camp, top)
		vec, err := uc.embedder.Encode(ctx, text)
		if err != nil {
			return 0, err
		}
		items = append(items, VectorItem{
			CampID:   camp.ID,
			Vec:      vec,
			TextHash: textHash(text),
		})
	}

	return uc.vectors.UpsertMany(ctx, items)
}

// buildEmbedText mirrors Python `domain.embed_text.build_embed_text` —
// concatenates a fixed projection of camp fields with up to 5 review excerpts.
// The exact wording isn't load-bearing for byte-equal regression (this code
// path runs offline and produces a vector, not a JSON response) but staying
// close to Python keeps cross-cluster KNN behaviour consistent.
func buildEmbedText(c *domain.Camp, reviews []*domain.Review) string {
	var parts []string
	parts = append(parts, c.Name)
	if c.Region.Sido != "" || c.Region.Sigungu != "" {
		parts = append(parts, c.Region.Sido+" "+c.Region.Sigungu)
	}
	if c.Brief != nil && *c.Brief != "" {
		parts = append(parts, *c.Brief)
	}
	if c.LocationBrief != nil && *c.LocationBrief != "" {
		parts = append(parts, *c.LocationBrief)
	}
	if c.Description != nil && *c.Description != "" {
		parts = append(parts, *c.Description)
	}
	if len(c.Hashtags) > 0 {
		parts = append(parts, strings.Join(c.Hashtags, " "))
	}
	for _, r := range reviews {
		if r != nil && r.Text != "" {
			parts = append(parts, r.Text)
		}
	}
	return strings.Join(parts, "\n")
}

// textHash mirrors Python `domain.embed_text.text_hash` — SHA-1 hex digest.
func textHash(s string) string {
	h := sha1.Sum([]byte(s))
	return hex.EncodeToString(h[:])
}
