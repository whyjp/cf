// EtaProvider port — mirrors Python `cf_be_api.ports.eta.EtaProvider`.
//
// In Python the implementation is `EtagoSubprocessProvider` (forks the etago
// CLI). In Go (post-D-5) the implementation is the in-process
// adapters/eta.RouterProvider — same interface, no subprocess.
package ports

import (
	"context"

	"github.com/whyjp/cf/be-api/internal/domain"
)

// EtaDest pairs a stable id (camp_id at the use-case layer) with the Korean
// place name the eta provider geocodes + routes against. The id round-trips
// the result so the caller can map back without re-keying by place text.
type EtaDest struct {
	ID    string
	Place string
}

// EtaProvider computes drive-time minutes from one origin to one or many
// destination place names. Implementations honor ctx for both timeout and
// cancellation. A None-equivalent (zero Minutes pointer) result is paired
// with a non-empty Error so callers can surface "ok with no minutes" vs
// "failed" without inspecting Source.
type EtaProvider interface {
	// DriveEta resolves a single (origin → dest) pair. Returns an EtaResult
	// with Minutes=nil + Error set when no path is found.
	DriveEta(ctx context.Context, origin, dest string, timeoutS float64) (*domain.EtaResult, error)

	// DriveEtaBatch fans out N (id, place) pairs to a shared origin in
	// parallel up to `concurrency` simultaneous in-flight requests. Each
	// call honors `timeoutS` per item. Returned map is keyed by EtaDest.ID
	// (NOT by place text — places repeat across camps).
	DriveEtaBatch(ctx context.Context, origin string, dests []EtaDest, concurrency int, timeoutS float64) (map[string]*domain.EtaResult, error)
}

// EtaCache is the (origin, dest) → minutes lookup persisted across requests.
// Mirrors `cf_be_api.adapters.postgres.eta_cache_repo.PostgresEtaCacheRepo`.
type EtaCache interface {
	Get(ctx context.Context, origin, dest string) (minutes int, source string, ok bool, err error)
	Put(ctx context.Context, origin, dest string, minutes *int, source string) error
	Clear(ctx context.Context) (int64, error)
}
