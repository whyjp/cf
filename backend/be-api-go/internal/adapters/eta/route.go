package eta

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/whyjp/cf/be-api-go/internal/adapters/eta/parse"
)

// PerSourceTimeout caps each provider attempt. The total wall clock for a
// fallback chain is bounded by the caller's ctx (be-api default 12s, see
// /eta?timeout_s=…), so this constant keeps any single hung provider from
// consuming the whole budget.
const PerSourceTimeout = 6 * time.Second

// GetDuration walks providers sequentially. The first one that yields a
// non-zero Duration wins; ErrInputRejected short-circuits without trying
// further providers because a 4xx-class response means the *user input* is
// the problem, not the upstream.
func GetDuration(ctx context.Context, in parse.NormalizedInput, providers []Provider) (Duration, error) {
	if len(providers) == 0 {
		return Duration{}, errors.New("no providers configured")
	}
	var errs []string
	for _, p := range providers {
		sub, cancel := context.WithTimeout(ctx, PerSourceTimeout)
		d, err := p.Lookup(sub, in)
		cancel()
		if err == nil && d.Min > 0 {
			return d, nil
		}
		if errors.Is(err, ErrInputRejected) {
			return Duration{}, err
		}
		if err == nil {
			err = ErrEmptyPath
		}
		errs = append(errs, fmt.Sprintf("%s: %v", p.Name(), err))
	}
	return Duration{}, fmt.Errorf("%w: %s", ErrAllSourcesFail, strings.Join(errs, "; "))
}
