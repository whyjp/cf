package eta

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"

	"github.com/whyjp/cf/be-api/internal/adapters/eta/parse"
)

// KakaoProvider resolves place names against Kakao Map's anonymous public
// search endpoint (`search.map.kakao.com/mapsearch/map.daum`) — the only
// no-auth Kakao endpoint that still ships JSON as of 2026-05.
//
// Kakao's own routing endpoints (`apis-navi.kakaomobility.com`, the
// in-page XHRs at `map.kakao.com`) all require an app key, so the *time
// value* is computed by the OSRM helper after Kakao yields coordinates.
// The Source field is "kakao" because the geocoder is what makes a
// Korean place name resolve at all; etago/-verbose surfaces the OSRM
// step on stderr.
type KakaoProvider struct {
	HTTP       *http.Client
	UserAgent  string
	SearchBase string
	Router     *OSRM
}

func NewKakaoProvider(client *http.Client, ua string) *KakaoProvider {
	return &KakaoProvider{
		HTTP:       client,
		UserAgent:  ua,
		SearchBase: "https://search.map.kakao.com/mapsearch/map.daum",
		Router:     NewOSRM(client),
	}
}

func (k *KakaoProvider) Name() string { return "kakao" }

func (k *KakaoProvider) Lookup(ctx context.Context, in parse.NormalizedInput) (Duration, error) {
	start := time.Now()

	sLat, sLng, err := k.Geocode(ctx, in.Start)
	if err != nil {
		return Duration{}, fmt.Errorf("kakao geocode start: %w", err)
	}
	eLat, eLng, err := k.Geocode(ctx, in.End)
	if err != nil {
		return Duration{}, fmt.Errorf("kakao geocode end: %w", err)
	}
	mins, err := k.Router.DurationMin(ctx, sLat, sLng, eLat, eLng)
	if err != nil {
		return Duration{}, err
	}
	return Duration{
		Min:       mins,
		Source:    "kakao",
		LatencyMs: int(time.Since(start).Milliseconds()),
	}, nil
}

// Geocoder is the minimal interface for resolving a Korean place name
// into (lat, lng). NaverProvider uses this when it owns NCP credentials
// for Directions 5 but the same NCP Application has no Geocoding
// service enabled — Kakao's anonymous K1 endpoint stands in.
type Geocoder interface {
	Geocode(ctx context.Context, query string) (lat, lng float64, err error)
}

// kakaoSearchEnvelope is the slice of the response we actually consume.
// The full response is ~50 KB with dozens of unrelated fields; we ignore
// everything except `place[0].lat / .lon` which Kakao serves as float64.
type kakaoSearchEnvelope struct {
	Place []struct {
		Lat  float64 `json:"lat"`
		Lon  float64 `json:"lon"`
		Name string  `json:"name"`
	} `json:"place"`
}

// Geocode resolves a Korean place name via Kakao's anonymous K1 search
// endpoint. Exposed (capitalized) so other providers (notably the
// Naver NCP path when its Application lacks Geocoding) can borrow it.
func (k *KakaoProvider) Geocode(ctx context.Context, query string) (lat, lng float64, err error) {
	u, _ := url.Parse(k.SearchBase)
	q := u.Query()
	q.Set("q", query)
	u.RawQuery = q.Encode()

	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	req.Header.Set("User-Agent", k.UserAgent)
	req.Header.Set("Accept", "application/json, text/plain, */*")
	req.Header.Set("Accept-Language", "ko-KR,ko;q=0.9")
	req.Header.Set("Referer", "https://map.kakao.com/")

	resp, err := k.HTTP.Do(req)
	if err != nil {
		return 0, 0, fmt.Errorf("%w: %v", ErrUpstreamFail, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 500 {
		return 0, 0, ErrUpstreamFail
	}
	if resp.StatusCode >= 400 {
		return 0, 0, ErrInputRejected
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return 0, 0, ErrUpstreamFail
	}
	var env kakaoSearchEnvelope
	if err := json.Unmarshal(body, &env); err != nil {
		return 0, 0, fmt.Errorf("%w: kakao search: %v", ErrParseSchema, err)
	}
	if len(env.Place) == 0 || (env.Place[0].Lat == 0 && env.Place[0].Lon == 0) {
		return 0, 0, fmt.Errorf("%w: no place match for %q", ErrEmptyPath, query)
	}
	return env.Place[0].Lat, env.Place[0].Lon, nil
}
