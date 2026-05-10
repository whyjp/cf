// Package eta fetches drive ETA from public endpoints of Korean map
// services (Naver NCP Directions 5, Kakao K1 + OSRM) and orchestrates
// fallback between them. Absorbed from the standalone `etago` Go binary
// in SP-D D-5; the be-api now embeds providers directly and serves
// /eta /eta/batch /eta/cache.
package eta

import (
	"context"
	"errors"

	"github.com/whyjp/cf/be-api-go/internal/adapters/eta/parse"
)

// Duration is the unit result. LatencyMs records the adapter-side wall
// time for tracing/observability — the CLI used it for --verbose; in
// the be-api it surfaces in structured logs.
type Duration struct {
	Min       int
	Source    string
	LatencyMs int
}

// Provider is the contract every map adapter implements. Lookup is expected
// to honor ctx for both timeout and cancellation propagation; returning a
// non-nil error must leave Duration zero.
type Provider interface {
	Name() string
	Lookup(ctx context.Context, in parse.NormalizedInput) (Duration, error)
}

// Sentinel errors. Callers inspect via errors.Is. The original etago CLI
// mapped these to exit codes (input → 2, external → 3, unknown → 1); the
// be-api uses them to choose HTTP status (4xx vs 5xx) per route.
var (
	ErrEmptyPath      = errors.New("provider returned empty route")
	ErrInputRejected  = errors.New("provider rejected input")
	ErrUpstreamFail   = errors.New("upstream service failed")
	ErrAllSourcesFail = errors.New("all map sources failed")
	ErrParseSchema    = errors.New("response schema parse failed")
)
