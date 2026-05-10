// Embedder port — text → fixed-dim float vector.
//
// 1:1 with the Python `cf_be_api.ports.embed.Embedder` interface. Adapter
// implementations live in `internal/adapters/embed/`. The Go wrapper around
// ONNX Runtime + sugarme/tokenizer is `embed.OnnxEmbedder`.
package ports

import "context"

// Embedder turns a single text input into a fixed-dimension float vector.
//
// Implementations may hold heavy resources (ONNX session, tokenizer) and MUST
// be Closed when no longer needed. Implementations are expected to be
// goroutine-safe at the Encode level (the underlying ORT session is the
// concurrency bottleneck — a single shared instance is the typical layout).
type Embedder interface {
	Encode(ctx context.Context, text string) ([]float32, error)
	Close() error
}
