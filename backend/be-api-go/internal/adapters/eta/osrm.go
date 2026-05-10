package route

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
)

// OSRM is a thin client for the public OSRM demo router. It is *not* a
// Provider on its own — it's an internal helper used by Naver/Kakao
// adapters to compute drive ETA after they've resolved the start/end
// coordinates against their own geocoders. OSRM is anonymous (no key,
// no cookie); it uses OpenStreetMap data which has solid Korean coverage.
//
// As of 2026-05 this is the only realistic no-auth source of a numeric
// drive duration for Korean coordinates — Naver and Kakao have moved
// every routing endpoint behind app keys.
type OSRM struct {
	HTTP    *http.Client
	BaseURL string // default: https://router.project-osrm.org
}

func NewOSRM(client *http.Client) *OSRM {
	return &OSRM{HTTP: client, BaseURL: "https://router.project-osrm.org"}
}

// DurationMin returns the rounded minute count for driving from
// (sLat,sLng) to (eLat,eLng). Errors map to the route package sentinels:
// ErrUpstreamFail for transport/5xx, ErrEmptyPath for routes with
// zero/missing duration, ErrParseSchema for malformed responses.
func (o *OSRM) DurationMin(ctx context.Context, sLat, sLng, eLat, eLng float64) (int, error) {
	url := fmt.Sprintf("%s/route/v1/driving/%.6f,%.6f;%.6f,%.6f?overview=false",
		o.BaseURL, sLng, sLat, eLng, eLat)

	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "etago/1.0 (+https://github.com/whyjp/etago)")

	resp, err := o.HTTP.Do(req)
	if err != nil {
		return 0, fmt.Errorf("%w: osrm: %v", ErrUpstreamFail, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 500 {
		return 0, fmt.Errorf("%w: osrm http %d", ErrUpstreamFail, resp.StatusCode)
	}
	if resp.StatusCode >= 400 {
		return 0, fmt.Errorf("%w: osrm http %d", ErrInputRejected, resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return 0, ErrUpstreamFail
	}

	var env struct {
		Code   string `json:"code"`
		Routes []struct {
			Duration float64 `json:"duration"` // seconds
		} `json:"routes"`
	}
	if err := json.Unmarshal(body, &env); err != nil {
		return 0, fmt.Errorf("%w: osrm: %v", ErrParseSchema, err)
	}
	if env.Code != "Ok" || len(env.Routes) == 0 {
		return 0, ErrEmptyPath
	}
	secs := env.Routes[0].Duration
	if secs <= 0 {
		return 0, ErrEmptyPath
	}
	return int(math.Round(secs / 60)), nil
}
