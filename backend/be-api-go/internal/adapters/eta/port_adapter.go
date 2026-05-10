// port_adapter.go — wraps the in-package Provider chain in the
// ports.EtaProvider interface so the use-case layer doesn't depend on
// adapters/eta types directly.
//
// In Python this layer is `EtagoSubprocessProvider` (in adapters/eta/);
// here it's the same Provider chain that backed the standalone etago CLI,
// just called in-process with no fork.

package eta

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/whyjp/cf/be-api-go/internal/adapters/eta/parse"
	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

// RouterProvider implements ports.EtaProvider by walking a chain of
// in-package Provider implementations (typically Naver-NCP first,
// Kakao+OSRM second when NCP keys are present; reverse order otherwise).
type RouterProvider struct {
	chain []Provider
}

// Compile-time assertion.
var _ ports.EtaProvider = (*RouterProvider)(nil)

// NewRouterProvider wires a RouterProvider over the supplied chain. Pass
// providers in fallback order — the first that yields a non-zero Duration
// wins (see GetDuration).
func NewRouterProvider(chain []Provider) *RouterProvider {
	return &RouterProvider{chain: chain}
}

// DriveEta resolves a single (origin → dest) pair. Maps eta sentinels:
//
//   - ErrInputRejected → result with Minutes=nil, Error="rejected: …"
//   - ErrAllSourcesFail / ErrEmptyPath → Minutes=nil, Error="<provider>: …"
//   - ctx-deadline → Minutes=nil, Error="timeout"
//
// We return nil error in all the above; the use-case treats a non-nil
// EtaResult.Error as the failure signal. Truly unexpected errors (nil
// chain, etc.) come back as a non-nil error.
func (r *RouterProvider) DriveEta(ctx context.Context, origin, dest string, timeoutS float64) (*domain.EtaResult, error) {
	in, perr := parse.NormalizeInputs(origin, dest)
	if perr != nil {
		msg := perr.Error()
		return &domain.EtaResult{Origin: origin, Dest: dest, Error: &msg}, nil
	}
	if len(r.chain) == 0 {
		return nil, errors.New("no providers configured")
	}
	subCtx, cancel := context.WithTimeout(ctx, timeoutDuration(timeoutS))
	defer cancel()
	d, err := GetDuration(subCtx, in, r.chain)
	if err != nil {
		msg := truncErr(err.Error())
		return &domain.EtaResult{Origin: origin, Dest: dest, Error: &msg}, nil
	}
	mins := d.Min
	src := d.Source
	return &domain.EtaResult{
		Origin:  origin,
		Dest:    dest,
		Minutes: &mins,
		Source:  &src,
	}, nil
}

// DriveEtaBatch fans out items across goroutines bounded by `concurrency`.
// Each item carries its own per-item timeout; the parent ctx still bounds
// total wall clock. Output is keyed by EtaDest.ID (caller-supplied stable
// id, typically camp_id).
func (r *RouterProvider) DriveEtaBatch(
	ctx context.Context, origin string, dests []ports.EtaDest,
	concurrency int, timeoutS float64,
) (map[string]*domain.EtaResult, error) {
	if concurrency < 1 {
		concurrency = 1
	}
	out := make(map[string]*domain.EtaResult, len(dests))
	if len(dests) == 0 {
		return out, nil
	}
	var mu sync.Mutex
	sem := make(chan struct{}, concurrency)
	var wg sync.WaitGroup
	for _, d := range dests {
		d := d
		if d.Place == "" {
			msg := "empty place"
			mu.Lock()
			out[d.ID] = &domain.EtaResult{Origin: origin, Dest: d.Place, Error: &msg}
			mu.Unlock()
			continue
		}
		sem <- struct{}{}
		wg.Add(1)
		go func() {
			defer wg.Done()
			defer func() { <-sem }()
			res, err := r.DriveEta(ctx, origin, d.Place, timeoutS)
			if err != nil {
				msg := truncErr(err.Error())
				res = &domain.EtaResult{Origin: origin, Dest: d.Place, Error: &msg}
			}
			mu.Lock()
			out[d.ID] = res
			mu.Unlock()
		}()
	}
	wg.Wait()
	return out, nil
}

func timeoutDuration(s float64) time.Duration {
	if s <= 0 {
		return 12 * time.Second
	}
	return time.Duration(s * float64(time.Second))
}

func truncErr(msg string) string {
	const max = 200
	if len(msg) > max {
		return msg[:max]
	}
	return msg
}

// KakaoGeocoder implements ports.Geocoder by delegating to KakaoProvider's
// anonymous K1 search endpoint. The returned GeoPoint is nil when Kakao
// returns an empty match (NOT an error — the use-case treats nil as
// "skip the haversine pre-filter for this origin").
type KakaoGeocoder struct {
	kp *KakaoProvider
}

// Compile-time assertion.
var _ ports.Geocoder = (*KakaoGeocoder)(nil)

// NewKakaoGeocoder wraps an existing KakaoProvider for the Geocoder port.
func NewKakaoGeocoder(kp *KakaoProvider) *KakaoGeocoder {
	return &KakaoGeocoder{kp: kp}
}

// Lookup matches the Python Geocoder.lookup contract: nil + nil error for
// "no match" so callers can distinguish from upstream failures.
func (g *KakaoGeocoder) Lookup(ctx context.Context, address string) (*domain.GeoPoint, error) {
	if g.kp == nil {
		return nil, nil
	}
	lat, lon, err := g.kp.Geocode(ctx, address)
	if err != nil {
		// ErrEmptyPath = "no match" → nil, nil (parity with Python).
		if errors.Is(err, ErrEmptyPath) {
			return nil, nil
		}
		// Any other classification (auth, 5xx, parse) propagates so the
		// use-case can decide whether to surface a warning.
		return nil, fmt.Errorf("kakao geocode: %w", err)
	}
	return &domain.GeoPoint{Lat: lat, Lon: lon}, nil
}
