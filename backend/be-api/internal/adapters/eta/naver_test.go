package eta

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/whyjp/cf/be-api/internal/adapters/eta/parse"
)

func mkNaverInput(t *testing.T) parse.NormalizedInput {
	t.Helper()
	in, err := parse.NormalizeInputs("강남역", "수원시청")
	if err != nil {
		t.Fatal(err)
	}
	return in
}

func TestNaver_implementsProvider(t *testing.T) {
	var _ Provider = (*NaverProvider)(nil)
}

func TestNaver_endToEnd_naverGeocode_osrmRoute(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.Contains(r.URL.Path, "instant-search"):
			w.Header().Set("Content-Type", "application/json")
			w.Write([]byte(`{"place":{"items":[{"y":37.4979,"x":127.0276,"name":"강남역"}]}}`))
		case strings.Contains(r.URL.Path, "/route/v1/driving/"):
			w.Header().Set("Content-Type", "application/json")
			fmt.Fprintf(w, `{"code":"Ok","routes":[{"duration":%d}]}`, 3480)
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()
	n := &NaverProvider{
		HTTP:       srv.Client(),
		UserAgent:  "test",
		SearchBase: srv.URL + "/instant-search",
		Router:     &OSRM{HTTP: srv.Client(), BaseURL: srv.URL},
	}
	d, err := n.Lookup(context.Background(), mkNaverInput(t))
	if err != nil {
		t.Fatal(err)
	}
	if d.Source != "naver" || d.Min != 58 {
		t.Errorf("got %+v, want Source=naver Min=58", d)
	}
}

func TestNaver_captchaResponse_returnsEmptyPath(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"result":{"metaInfo":{"pageId":"ncaptcha-all-search-no-result"}},"ncaptcha":{"uuid":"x"}}`))
	}))
	defer srv.Close()
	n := &NaverProvider{HTTP: srv.Client(), UserAgent: "t", SearchBase: srv.URL, Router: NewOSRM(srv.Client())}
	_, err := n.Lookup(context.Background(), mkNaverInput(t))
	if !errors.Is(err, ErrEmptyPath) {
		t.Fatalf("want ErrEmptyPath (captcha), got %v", err)
	}
}

func TestNaver_5xx_returnsUpstream(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(503)
	}))
	defer srv.Close()
	n := &NaverProvider{HTTP: srv.Client(), UserAgent: "t", SearchBase: srv.URL, Router: NewOSRM(srv.Client())}
	_, err := n.Lookup(context.Background(), mkNaverInput(t))
	if !errors.Is(err, ErrUpstreamFail) {
		t.Fatalf("want ErrUpstreamFail, got %v", err)
	}
}

func TestNaver_4xx_returnsInputRejected(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(400)
	}))
	defer srv.Close()
	n := &NaverProvider{HTTP: srv.Client(), UserAgent: "t", SearchBase: srv.URL, Router: NewOSRM(srv.Client())}
	_, err := n.Lookup(context.Background(), mkNaverInput(t))
	if !errors.Is(err, ErrInputRejected) {
		t.Fatalf("want ErrInputRejected, got %v", err)
	}
}

func TestNaver_extractFirstCoord_strings(t *testing.T) {
	body := []byte(`{"items":[{"y":"37.5","x":"127.0"}]}`)
	lat, lng, ok := extractFirstCoord(body)
	if !ok || lat != 37.5 || lng != 127.0 {
		t.Errorf("got lat=%v lng=%v ok=%v", lat, lng, ok)
	}
}

func TestNaver_extractFirstCoord_zerosTreatedAsMiss(t *testing.T) {
	body := []byte(`{"items":[{"y":0,"x":0},{"y":37.5,"x":127.0}]}`)
	lat, lng, ok := extractFirstCoord(body)
	if !ok || lat != 37.5 || lng != 127.0 {
		t.Errorf("got lat=%v lng=%v ok=%v", lat, lng, ok)
	}
}
