// Package route fetches drive ETA from anonymous public web endpoints of
// Korean map services and orchestrates fallback between them.
package route

import (
	"context"
	"errors"

	"github.com/whyjp/etago/internal/parse"
)

// Duration is the unit result returned to the CLI. LatencyMs records the
// adapter-side wall time so --verbose can attribute slowness without the CLI
// having to instrument its own timer.
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

// Sentinel errors. Callers (CLI/main) inspect via errors.Is to map exit codes:
// input → 2, external → 3, unknown → 1.
var (
	ErrEmptyPath      = errors.New("provider returned empty route")
	ErrInputRejected  = errors.New("provider rejected input")
	ErrUpstreamFail   = errors.New("upstream service failed")
	ErrAllSourcesFail = errors.New("all map sources failed")
	ErrParseSchema    = errors.New("response schema parse failed")
)
