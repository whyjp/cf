package eta

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// kakaoMockSearchAndRouter wires a Kakao geocode mock + OSRM router mock
// onto the same httptest server, dispatched by URL path.
func kakaoMockSearchAndRouter(t *testing.T, durationSec int) (*KakaoProvider, *httptest.Server) {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.Contains(r.URL.Path, "mapsearch"):
			w.Header().Set("Content-Type", "application/json")
			fmt.Fprintf(w, `{"place":[{"lat":37.4979,"lon":127.0276,"name":"강남역"}]}`)
		case strings.Contains(r.URL.Path, "/route/v1/driving/"):
			w.Header().Set("Content-Type", "application/json")
			fmt.Fprintf(w, `{"code":"Ok","routes":[{"duration":%d}]}`, durationSec)
		default:
			http.NotFound(w, r)
		}
	}))
	t.Cleanup(srv.Close)
	k := &KakaoProvider{
		HTTP:       srv.Client(),
		UserAgent:  "test",
		SearchBase: srv.URL + "/mapsearch/map.daum",
		Router:     &OSRM{HTTP: srv.Client(), BaseURL: srv.URL},
	}
	return k, srv
}

func TestKakao_implementsProvider(t *testing.T) {
	var _ Provider = (*KakaoProvider)(nil)
}

func TestKakao_endToEnd_kakaoGeocode_osrmRoute(t *testing.T) {
	k, _ := kakaoMockSearchAndRouter(t, 3480)
	in := mkNaverInput(t)
	d, err := k.Lookup(context.Background(), in)
	if err != nil {
		t.Fatal(err)
	}
	if d.Source != "kakao" {
		t.Errorf("source: got %q want kakao", d.Source)
	}
	if d.Min != 58 {
		t.Errorf("min: got %d want 58", d.Min)
	}
}

func TestKakao_5xx_returnsUpstream(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(502)
	}))
	defer srv.Close()
	k := &KakaoProvider{HTTP: srv.Client(), UserAgent: "t", SearchBase: srv.URL, Router: NewOSRM(srv.Client())}
	_, err := k.Lookup(context.Background(), mkNaverInput(t))
	if !errors.Is(err, ErrUpstreamFail) {
		t.Fatalf("want ErrUpstreamFail, got %v", err)
	}
}

func TestKakao_emptyPlace_returnsEmptyPath(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"place":[]}`))
	}))
	defer srv.Close()
	k := &KakaoProvider{HTTP: srv.Client(), UserAgent: "t", SearchBase: srv.URL, Router: NewOSRM(srv.Client())}
	_, err := k.Lookup(context.Background(), mkNaverInput(t))
	if !errors.Is(err, ErrEmptyPath) {
		t.Fatalf("want ErrEmptyPath, got %v", err)
	}
}
