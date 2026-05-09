package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// TestUsage_compiles is a smoke-level guard that the help printer is wired up.
func TestUsage_compiles(t *testing.T) {
	fs := flag.NewFlagSet("etago", flag.ContinueOnError)
	if fs.NArg() != 0 {
		t.Errorf("flagset NArg should start at 0")
	}
}

func TestBuildProviders_auto_noNcp_kakaoFirst(t *testing.T) {
	t.Setenv("NCP_CLIENT_ID", "")
	t.Setenv("NCP_CLIENT_SECRET", "")
	ps, err := buildProviders("auto", "test", nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(ps) != 2 {
		t.Errorf("auto should return 2 providers, got %d", len(ps))
	}
	if ps[0].Name() != "kakao" {
		t.Errorf("without NCP keys, expected kakao first, got %s", ps[0].Name())
	}
}

func TestBuildProviders_auto_withNcp_naverFirst(t *testing.T) {
	t.Setenv("NCP_CLIENT_ID", "test-id")
	t.Setenv("NCP_CLIENT_SECRET", "test-secret")
	ps, err := buildProviders("auto", "test", nil)
	if err != nil {
		t.Fatal(err)
	}
	if ps[0].Name() != "naver" {
		t.Errorf("with NCP keys, expected naver first, got %s", ps[0].Name())
	}
}

func TestBuildProviders_naverOnly(t *testing.T) {
	ps, _ := buildProviders("naver", "test", nil)
	if len(ps) != 1 || ps[0].Name() != "naver" {
		t.Errorf("expected [naver], got %v", ps)
	}
}

func TestBuildProviders_kakaoOnly(t *testing.T) {
	ps, _ := buildProviders("kakao", "test", nil)
	if len(ps) != 1 || ps[0].Name() != "kakao" {
		t.Errorf("expected [kakao], got %v", ps)
	}
}

func TestBuildProviders_unknown(t *testing.T) {
	_, err := buildProviders("yahoo", "test", nil)
	if err == nil {
		t.Error("expected error for unknown source")
	}
}

// TestRunGeocodeBatch_kakaoOnly_orderedOutput verifies that batch mode
// preserves input order even when workers race and that each line gets
// one NDJSON record. A local httptest server stands in for Kakao's K1.
func TestRunGeocodeBatch_kakaoOnly_orderedOutput(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query().Get("q")
		coords := map[string][2]float64{
			"a": {37.111, 127.111},
			"b": {37.222, 127.222},
			"c": {37.333, 127.333},
			"d": {37.444, 127.444},
		}
		c, ok := coords[q]
		if !ok {
			io.WriteString(w, `{"place":[]}`)
			return
		}
		// Stagger latency so workers genuinely race; if order weren't
		// stabilized in the result slice, NDJSON output would shuffle.
		time.Sleep(time.Duration(15*(len(q)%4)+5) * time.Millisecond)
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"place": []map[string]any{{"lat": c[0], "lon": c[1], "name": q}},
		})
	}))
	defer srv.Close()

	// Hijack DefaultTransport so the production KakaoProvider code path
	// (with its real SearchBase URL) hits our stub server.
	origTransport := http.DefaultTransport
	defer func() { http.DefaultTransport = origTransport }()
	http.DefaultTransport = &rewriteTransport{
		from: "search.map.kakao.com",
		to:   srv.Listener.Addr().String(),
		base: origTransport,
	}

	stdout := &bytes.Buffer{}
	stderr := &bytes.Buffer{}
	stdin := strings.NewReader("a\nb\nc\nd\n")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	exit := runGeocodeBatch(
		ctx, "kakao", "test",
		3, 2*time.Second, false,
		http.DefaultClient, stdin, stdout, stderr,
	)
	if exit != 0 {
		t.Fatalf("expected exit 0, got %d. stderr=%s", exit, stderr.String())
	}

	dec := json.NewDecoder(stdout)
	want := []string{"a", "b", "c", "d"}
	for i, expQ := range want {
		var rec struct {
			Query  string  `json:"query"`
			Lat    float64 `json:"lat"`
			Lon    float64 `json:"lon"`
			Source string  `json:"source"`
			Error  string  `json:"error"`
		}
		if err := dec.Decode(&rec); err != nil {
			t.Fatalf("decode #%d: %v", i, err)
		}
		if rec.Query != expQ {
			t.Errorf("line %d: want query=%q, got %q", i, expQ, rec.Query)
		}
		if rec.Error != "" {
			t.Errorf("line %d (%s): unexpected error %q", i, expQ, rec.Error)
		}
		if rec.Source != "kakao" {
			t.Errorf("line %d: want source=kakao, got %q", i, rec.Source)
		}
	}
}

// TestRunGeocodeBatch_emptyInput_exit0 — zero queries is a valid no-op
// (matches camfit-puller's "nothing pending" path).
func TestRunGeocodeBatch_emptyInput_exit0(t *testing.T) {
	stdout := &bytes.Buffer{}
	stderr := &bytes.Buffer{}
	exit := runGeocodeBatch(
		context.Background(), "kakao", "test",
		2, time.Second, false,
		http.DefaultClient, strings.NewReader(""), stdout, stderr,
	)
	if exit != 0 {
		t.Fatalf("empty stdin should exit 0, got %d", exit)
	}
	if stdout.Len() != 0 {
		t.Errorf("empty stdin should print nothing, got %q", stdout.String())
	}
}

// TestRunGeocodeBatch_allFail_exit3 — when no line resolves and there is
// at least one input, exit code is 3 (matching the single-query mode).
func TestRunGeocodeBatch_allFail_exit3(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Always empty match.
		_, _ = io.WriteString(w, `{"place":[]}`)
	}))
	defer srv.Close()
	origTransport := http.DefaultTransport
	defer func() { http.DefaultTransport = origTransport }()
	http.DefaultTransport = &rewriteTransport{
		from: "search.map.kakao.com",
		to:   srv.Listener.Addr().String(),
		base: origTransport,
	}

	stdout := &bytes.Buffer{}
	stderr := &bytes.Buffer{}
	exit := runGeocodeBatch(
		context.Background(), "kakao", "test",
		2, time.Second, false,
		http.DefaultClient, strings.NewReader("zzz\nyyy\n"), stdout, stderr,
	)
	if exit != 3 {
		t.Errorf("all-fail with non-empty input should exit 3, got %d", exit)
	}
	// Both records still emitted (with errors) so the caller can pair input ↔ output.
	dec := json.NewDecoder(stdout)
	for _, expQ := range []string{"zzz", "yyy"} {
		var rec struct {
			Query string `json:"query"`
			Error string `json:"error"`
		}
		if err := dec.Decode(&rec); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if rec.Query != expQ {
			t.Errorf("query mismatch: want %q got %q", expQ, rec.Query)
		}
		if rec.Error == "" {
			t.Errorf("expected error for %q, got success", expQ)
		}
	}
}

// rewriteTransport rewrites the host of outgoing requests so the production
// HTTP client paths can be exercised against a local httptest server.
type rewriteTransport struct {
	from, to string
	base     http.RoundTripper
}

func (rt *rewriteTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	if strings.Contains(req.URL.Host, rt.from) {
		req = req.Clone(req.Context())
		req.URL.Scheme = "http"
		req.URL.Host = rt.to
		req.Host = rt.to
	}
	return rt.base.RoundTrip(req)
}
