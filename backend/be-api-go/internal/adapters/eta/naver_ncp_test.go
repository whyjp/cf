package route

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// ncpMockServer wires NCP geocode + direction handlers onto one server,
// dispatched by URL path.
func ncpMockServer(t *testing.T, durationMs int64, opts ...func(http.ResponseWriter, *http.Request)) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Honor opts override first
		for _, fn := range opts {
			fn(w, r)
			return
		}
		if r.Header.Get("X-NCP-APIGW-API-KEY-ID") == "" {
			http.Error(w, `{"error":"missing ncp id"}`, http.StatusUnauthorized)
			return
		}
		switch {
		case strings.Contains(r.URL.Path, "/map-geocode/"):
			w.Header().Set("Content-Type", "application/json")
			fmt.Fprintln(w, `{"status":"OK","meta":{"totalCount":1,"page":1,"count":1},"addresses":[{"x":"127.0276234","y":"37.4980854"}]}`)
		case strings.Contains(r.URL.Path, "/map-direction/"):
			w.Header().Set("Content-Type", "application/json")
			fmt.Fprintf(w, `{"code":0,"message":"ok","route":{"traoptimal":[{"summary":{"duration":%d}}]}}`, durationMs)
		default:
			http.NotFound(w, r)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func newNcpNaver(t *testing.T, srv *httptest.Server) *NaverProvider {
	t.Helper()
	return &NaverProvider{
		HTTP:            srv.Client(),
		UserAgent:       "test",
		SearchBase:      srv.URL + "/legacy",
		GeocodeBase:     srv.URL + "/map-geocode/v2/geocode",
		DirectionBase:   srv.URL + "/map-direction/v1/driving",
		NcpClientID:     "id-123",
		NcpClientSecret: "secret-abc",
		Router:          NewOSRM(srv.Client()),
	}
}

func TestNaverNcp_endToEnd(t *testing.T) {
	srv := ncpMockServer(t, 3480000) // 58 min in ms
	n := newNcpNaver(t, srv)
	d, err := n.Lookup(context.Background(), mkNaverInput(t))
	if err != nil {
		t.Fatal(err)
	}
	if d.Source != "naver" || d.Min != 58 {
		t.Errorf("got %+v, want Source=naver Min=58", d)
	}
}

func TestNaverNcp_HasNcp(t *testing.T) {
	n := &NaverProvider{}
	if n.HasNcp() {
		t.Error("empty creds should report HasNcp=false")
	}
	n.NcpClientID = "x"
	if n.HasNcp() {
		t.Error("only id set should report HasNcp=false")
	}
	n.NcpClientSecret = "y"
	if !n.HasNcp() {
		t.Error("both set should report HasNcp=true")
	}
}

func TestNaverNcp_401_returnsInputRejected(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer srv.Close()
	n := &NaverProvider{
		HTTP:            srv.Client(),
		UserAgent:       "t",
		GeocodeBase:     srv.URL + "/g",
		DirectionBase:   srv.URL + "/d",
		NcpClientID:     "id",
		NcpClientSecret: "secret",
		Router:          NewOSRM(srv.Client()),
	}
	_, err := n.Lookup(context.Background(), mkNaverInput(t))
	if !errors.Is(err, ErrUpstreamFail) {
		t.Fatalf("want ErrUpstreamFail (so chain falls through), got %v", err)
	}
	if !strings.Contains(err.Error(), "ncp auth") {
		t.Errorf("error should mention ncp auth, got: %v", err)
	}
}

func TestNaverNcp_zeroDuration_returnsEmptyPath(t *testing.T) {
	srv := ncpMockServer(t, 0)
	n := newNcpNaver(t, srv)
	_, err := n.Lookup(context.Background(), mkNaverInput(t))
	if !errors.Is(err, ErrEmptyPath) {
		t.Fatalf("want ErrEmptyPath, got %v", err)
	}
}

func TestNaverNcp_directionCodeNonZero_returnsEmptyPath(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.Contains(r.URL.Path, "/map-geocode/"):
			fmt.Fprintln(w, `{"addresses":[{"x":"127.0","y":"37.5"}]}`)
		case strings.Contains(r.URL.Path, "/map-direction/"):
			fmt.Fprintln(w, `{"code":1,"message":"no route"}`)
		}
	}))
	defer srv.Close()
	n := &NaverProvider{
		HTTP:            srv.Client(),
		UserAgent:       "t",
		GeocodeBase:     srv.URL + "/map-geocode/v2/geocode",
		DirectionBase:   srv.URL + "/map-direction/v1/driving",
		NcpClientID:     "id",
		NcpClientSecret: "secret",
	}
	_, err := n.Lookup(context.Background(), mkNaverInput(t))
	if !errors.Is(err, ErrEmptyPath) {
		t.Fatalf("want ErrEmptyPath, got %v", err)
	}
}

func TestNaverNcp_emptyAddresses_returnsEmptyPath(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintln(w, `{"status":"OK","addresses":[]}`)
	}))
	defer srv.Close()
	n := &NaverProvider{
		HTTP:            srv.Client(),
		UserAgent:       "t",
		GeocodeBase:     srv.URL,
		DirectionBase:   srv.URL,
		NcpClientID:     "id",
		NcpClientSecret: "secret",
	}
	_, err := n.Lookup(context.Background(), mkNaverInput(t))
	if !errors.Is(err, ErrEmptyPath) {
		t.Fatalf("want ErrEmptyPath, got %v", err)
	}
}
