package eta

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestOSRM_parsesDuration(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"code":"Ok","routes":[{"duration":3480}]}`))
	}))
	defer srv.Close()

	o := &OSRM{HTTP: srv.Client(), BaseURL: srv.URL}
	mins, err := o.DurationMin(context.Background(), 37.5, 127.0, 37.6, 127.1)
	if err != nil {
		t.Fatal(err)
	}
	if mins != 58 {
		t.Errorf("got %d, want 58", mins)
	}
}

func TestOSRM_emptyRoutes_returnsEmptyPath(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"code":"Ok","routes":[]}`))
	}))
	defer srv.Close()
	o := &OSRM{HTTP: srv.Client(), BaseURL: srv.URL}
	_, err := o.DurationMin(context.Background(), 37.5, 127.0, 37.6, 127.1)
	if !errors.Is(err, ErrEmptyPath) {
		t.Fatalf("want ErrEmptyPath, got %v", err)
	}
}

func TestOSRM_5xx_returnsUpstream(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(503)
	}))
	defer srv.Close()
	o := &OSRM{HTTP: srv.Client(), BaseURL: srv.URL}
	_, err := o.DurationMin(context.Background(), 37.5, 127.0, 37.6, 127.1)
	if !errors.Is(err, ErrUpstreamFail) {
		t.Fatalf("want ErrUpstreamFail, got %v", err)
	}
}

func TestOSRM_4xx_returnsInputRejected(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(400)
	}))
	defer srv.Close()
	o := &OSRM{HTTP: srv.Client(), BaseURL: srv.URL}
	_, err := o.DurationMin(context.Background(), 37.5, 127.0, 37.6, 127.1)
	if !errors.Is(err, ErrInputRejected) {
		t.Fatalf("want ErrInputRejected, got %v", err)
	}
}

func TestOSRM_zeroDuration_returnsEmptyPath(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"code":"Ok","routes":[{"duration":0}]}`))
	}))
	defer srv.Close()
	o := &OSRM{HTTP: srv.Client(), BaseURL: srv.URL}
	_, err := o.DurationMin(context.Background(), 37.5, 127.0, 37.6, 127.1)
	if !errors.Is(err, ErrEmptyPath) {
		t.Fatalf("want ErrEmptyPath, got %v", err)
	}
}
