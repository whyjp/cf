package route

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/url"
	"strconv"
	"time"

	"github.com/whyjp/etago/internal/parse"
)

// NaverProvider talks to the Naver Cloud Platform Maps APIs when NCP
// credentials are present, and otherwise falls back to the public web
// search endpoint paired with OSRM. The two modes share the Provider
// interface so the rest of the pipeline doesn't care which path runs.
//
// In NCP mode (NcpClientID + NcpClientSecret set) the time value comes
// from Naver's own Directions 5 traffic-aware engine — this is the
// genuine "Naver Map drive ETA" the original requirement asked for.
// Without keys, Naver's anonymous search is captcha-gated since 2024;
// the provider still implements that path so users see a clear,
// source-specific error and can fall through to Kakao+OSRM.
type NaverProvider struct {
	HTTP            *http.Client
	UserAgent       string
	SearchBase      string // anonymous fallback (captcha-prone)
	GeocodeBase     string // NCP geocode v2 (used only if Geocoder == nil)
	DirectionBase   string // NCP directions 5
	NcpClientID     string
	NcpClientSecret string
	Router          *OSRM    // used by the anonymous path only
	Geocoder        Geocoder // optional override for the NCP path —
	// if set, ncp coords come from here (e.g. Kakao K1) instead of
	// NCP geocoding. Lets users with a Directions-5-only NCP
	// Application still ship genuine Naver drive ETA.
}

// NewNaverProvider wires the live Naver endpoints. NCP credentials are
// read from the environment at construction time so a process that
// loads .env first picks them up automatically.
func NewNaverProvider(client *http.Client, ua string) *NaverProvider {
	return &NaverProvider{
		HTTP:            client,
		UserAgent:       ua,
		SearchBase:      "https://map.naver.com/p/api/search/instant-search",
		// NCP Maps APIs migrated host: naveropenapi.apigw.ntruss.com →
		// maps.apigw.ntruss.com. The legacy host now returns 403 even
		// for valid keys.
		GeocodeBase:   "https://maps.apigw.ntruss.com/map-geocode/v2/geocode",
		DirectionBase: "https://maps.apigw.ntruss.com/map-direction/v1/driving",
		NcpClientID:     readEnv("NCP_CLIENT_ID"),
		NcpClientSecret: readEnv("NCP_CLIENT_SECRET"),
		Router:          NewOSRM(client),
	}
}

func (n *NaverProvider) Name() string { return "naver" }

// HasNcp reports whether NCP credentials are loaded; callers can use
// this to decide chain ordering.
func (n *NaverProvider) HasNcp() bool {
	return n.NcpClientID != "" && n.NcpClientSecret != ""
}

func (n *NaverProvider) Lookup(ctx context.Context, in parse.NormalizedInput) (Duration, error) {
	if n.HasNcp() {
		return n.lookupNcp(ctx, in)
	}
	return n.lookupAnonymous(ctx, in)
}

// ---- NCP path (authoritative) -------------------------------------------------

func (n *NaverProvider) lookupNcp(ctx context.Context, in parse.NormalizedInput) (Duration, error) {
	start := time.Now()

	sLat, sLng, err := n.geocodeForNcp(ctx, in.Start)
	if err != nil {
		return Duration{}, fmt.Errorf("naver ncp geocode start: %w", err)
	}
	eLat, eLng, err := n.geocodeForNcp(ctx, in.End)
	if err != nil {
		return Duration{}, fmt.Errorf("naver ncp geocode end: %w", err)
	}
	mins, err := n.ncpDirections(ctx, sLat, sLng, eLat, eLng)
	if err != nil {
		return Duration{}, err
	}
	if mins <= 0 {
		return Duration{}, ErrEmptyPath
	}
	return Duration{
		Min:       mins,
		Source:    "naver",
		LatencyMs: int(time.Since(start).Milliseconds()),
	}, nil
}

// geocodeForNcp tries NCP Geocoding (which only matches road-name and
// jibun addresses) and falls back to the injected Geocoder (typically
// Kakao K1, which handles POIs/stations/landmarks) on ErrEmptyPath. The
// fallback only runs when a Geocoder is wired; otherwise the NCP error
// surfaces as-is.
func (n *NaverProvider) geocodeForNcp(ctx context.Context, query string) (lat, lng float64, err error) {
	lat, lng, err = n.ncpGeocode(ctx, query)
	if err == nil {
		return lat, lng, nil
	}
	if errors.Is(err, ErrEmptyPath) && n.Geocoder != nil {
		return n.Geocoder.Geocode(ctx, query)
	}
	return 0, 0, err
}

// ncpGeocodeEnvelope captures the slice of the response we use.
// `x` and `y` ship as strings in the live API.
type ncpGeocodeEnvelope struct {
	Status    string `json:"status"`
	Meta      struct {
		TotalCount int `json:"totalCount"`
	} `json:"meta"`
	Addresses []struct {
		X string `json:"x"` // lng (string)
		Y string `json:"y"` // lat (string)
	} `json:"addresses"`
	ErrorMessage string `json:"errorMessage"`
}

func (n *NaverProvider) ncpGeocode(ctx context.Context, query string) (lat, lng float64, err error) {
	u, _ := url.Parse(n.GeocodeBase)
	q := u.Query()
	q.Set("query", query)
	u.RawQuery = q.Encode()

	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	n.setNcpHeaders(req)

	resp, err := n.HTTP.Do(req)
	if err != nil {
		return 0, 0, fmt.Errorf("%w: %v", ErrUpstreamFail, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden {
		// Wrap as ErrUpstreamFail (not ErrInputRejected) so the chain
		// falls through to Kakao instead of short-circuiting. Auth
		// failure is a credential/console-config problem, not the
		// user's input.
		return 0, 0, fmt.Errorf("%w: ncp auth (status %d) — verify NCP console: "+
			"(1) Application 등록 → Service: Geocoding + Directions 5 checked, "+
			"(2) 서비스 환경 (IP/Web URL) allows this host, "+
			"(3) Maps service activated on the account",
			ErrUpstreamFail, resp.StatusCode)
	}
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
	var env ncpGeocodeEnvelope
	if err := json.Unmarshal(body, &env); err != nil {
		return 0, 0, fmt.Errorf("%w: ncp geocode: %v", ErrParseSchema, err)
	}
	if len(env.Addresses) == 0 {
		return 0, 0, fmt.Errorf("%w: ncp no match for %q", ErrEmptyPath, query)
	}
	lng, err = strconv.ParseFloat(env.Addresses[0].X, 64)
	if err != nil {
		return 0, 0, fmt.Errorf("%w: ncp x: %v", ErrParseSchema, err)
	}
	lat, err = strconv.ParseFloat(env.Addresses[0].Y, 64)
	if err != nil {
		return 0, 0, fmt.Errorf("%w: ncp y: %v", ErrParseSchema, err)
	}
	return lat, lng, nil
}

// ncpDirectionEnvelope picks just the duration field. Naver returns it
// in milliseconds at route.traoptimal[0].summary.duration.
type ncpDirectionEnvelope struct {
	Code         int    `json:"code"`
	Message      string `json:"message"`
	ErrorMessage string `json:"errorMessage"`
	Route        struct {
		Traoptimal []struct {
			Summary struct {
				Duration int64 `json:"duration"` // ms
			} `json:"summary"`
		} `json:"traoptimal"`
	} `json:"route"`
}

func (n *NaverProvider) ncpDirections(ctx context.Context, sLat, sLng, eLat, eLng float64) (int, error) {
	u, _ := url.Parse(n.DirectionBase)
	q := u.Query()
	q.Set("start", fmt.Sprintf("%.6f,%.6f", sLng, sLat))
	q.Set("goal", fmt.Sprintf("%.6f,%.6f", eLng, eLat))
	q.Set("option", "traoptimal")
	u.RawQuery = q.Encode()

	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	n.setNcpHeaders(req)

	resp, err := n.HTTP.Do(req)
	if err != nil {
		return 0, fmt.Errorf("%w: %v", ErrUpstreamFail, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden {
		return 0, fmt.Errorf("%w: ncp auth (status %d)", ErrUpstreamFail, resp.StatusCode)
	}
	if resp.StatusCode >= 500 {
		return 0, ErrUpstreamFail
	}
	if resp.StatusCode >= 400 {
		return 0, ErrInputRejected
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return 0, ErrUpstreamFail
	}
	var env ncpDirectionEnvelope
	if err := json.Unmarshal(body, &env); err != nil {
		return 0, fmt.Errorf("%w: ncp direction: %v", ErrParseSchema, err)
	}
	// code: 0 = found, non-0 = no route or other domain error
	if env.Code != 0 || len(env.Route.Traoptimal) == 0 {
		return 0, ErrEmptyPath
	}
	ms := env.Route.Traoptimal[0].Summary.Duration
	if ms <= 0 {
		return 0, ErrEmptyPath
	}
	return int(math.Round(float64(ms) / 60000)), nil
}

func (n *NaverProvider) setNcpHeaders(req *http.Request) {
	// NCP API Gateway documents these as lowercase. HTTP headers are
	// case-insensitive, but matching the docs avoids mismatch reports.
	req.Header.Set("x-ncp-apigw-api-key-id", n.NcpClientID)
	req.Header.Set("x-ncp-apigw-api-key", n.NcpClientSecret)
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", n.UserAgent)
}

// ---- Anonymous path (best-effort, usually captcha-blocked) -------------------

func (n *NaverProvider) lookupAnonymous(ctx context.Context, in parse.NormalizedInput) (Duration, error) {
	start := time.Now()

	sLat, sLng, err := n.geocodeAnon(ctx, in.Start)
	if err != nil {
		return Duration{}, fmt.Errorf("naver geocode start: %w", err)
	}
	eLat, eLng, err := n.geocodeAnon(ctx, in.End)
	if err != nil {
		return Duration{}, fmt.Errorf("naver geocode end: %w", err)
	}
	mins, err := n.Router.DurationMin(ctx, sLat, sLng, eLat, eLng)
	if err != nil {
		return Duration{}, err
	}
	return Duration{
		Min:       mins,
		Source:    "naver",
		LatencyMs: int(time.Since(start).Milliseconds()),
	}, nil
}

func (n *NaverProvider) geocodeAnon(ctx context.Context, query string) (lat, lng float64, err error) {
	u, _ := url.Parse(n.SearchBase)
	q := u.Query()
	q.Set("query", query)
	q.Set("type", "all")
	u.RawQuery = q.Encode()

	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	req.Header.Set("User-Agent", n.UserAgent)
	req.Header.Set("Accept", "application/json, text/plain, */*")
	req.Header.Set("Accept-Language", "ko-KR,ko;q=0.9")
	req.Header.Set("Referer", "https://map.naver.com/")

	resp, err := n.HTTP.Do(req)
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
	if lat, lng, ok := extractFirstCoord(body); ok {
		return lat, lng, nil
	}
	if isCaptchaResponse(body) {
		return 0, 0, fmt.Errorf("%w: naver captcha — set NCP_CLIENT_ID/NCP_CLIENT_SECRET to use the keyed path", ErrEmptyPath)
	}
	return 0, 0, fmt.Errorf("%w: no coord for %q", ErrParseSchema, query)
}

func isCaptchaResponse(body []byte) bool {
	var raw map[string]any
	if err := json.Unmarshal(body, &raw); err != nil {
		return false
	}
	if _, ok := raw["ncaptcha"]; ok {
		return true
	}
	if r, ok := raw["result"].(map[string]any); ok {
		if mi, ok := r["metaInfo"].(map[string]any); ok {
			if pid, _ := mi["pageId"].(string); pid == "ncaptcha-all-search-no-result" {
				return true
			}
		}
	}
	return false
}

func extractFirstCoord(body []byte) (lat, lng float64, ok bool) {
	var raw any
	if err := json.Unmarshal(body, &raw); err != nil {
		return 0, 0, false
	}
	return walkForLatLng(raw)
}

func walkForLatLng(node any) (lat, lng float64, ok bool) {
	switch v := node.(type) {
	case map[string]any:
		yRaw, hasY := v["y"]
		xRaw, hasX := v["x"]
		if hasY && hasX {
			if y, yok := numericFromAny(yRaw); yok {
				if x, xok := numericFromAny(xRaw); xok && y != 0 && x != 0 {
					return y, x, true
				}
			}
		}
		for _, child := range v {
			if lat, lng, ok = walkForLatLng(child); ok {
				return
			}
		}
	case []any:
		for _, item := range v {
			if lat, lng, ok = walkForLatLng(item); ok {
				return
			}
		}
	}
	return 0, 0, false
}

func numericFromAny(v any) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case json.Number:
		f, err := x.Float64()
		return f, err == nil
	case string:
		var f float64
		_, err := fmt.Sscanf(x, "%f", &f)
		return f, err == nil
	}
	return 0, false
}

// readEnv exists so tests can stub env reads without poking os.Getenv.
var readEnv = func(key string) string { return getenv(key) }
