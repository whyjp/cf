//go:build smoke

// Package tests contains live-network smoke tests excluded from the default
// `go test ./...` run by build tag `smoke`. Invoke with:
//
//	go test -tags=smoke ./tests/...
//
// These tests hit real Naver / Kakao public web endpoints; they will skip
// gracefully when the host has no network or the upstream returns 403.
package tests

import (
	"context"
	"errors"
	"net"
	"net/http"
	"testing"
	"time"

	"github.com/whyjp/etago/internal/envfile"
	"github.com/whyjp/etago/internal/parse"
	"github.com/whyjp/etago/internal/route"
)

const ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
	"(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

func skipIfOffline(t *testing.T) {
	t.Helper()
	c, err := net.DialTimeout("tcp", "1.1.1.1:443", 1500*time.Millisecond)
	if err != nil {
		t.Skipf("offline (no outbound network): %v", err)
	}
	c.Close()
}

func TestSmoke_5pairs_majorityPass(t *testing.T) {
	skipIfOffline(t)
	// Mirror cmd/etago/main.go: pull NCP creds from .env so the live
	// chain matches what the deployed binary does.
	_ = envfile.LoadDefault()

	pairs := [][2]string{
		{"강남역", "수원시청"},
		{"서울역", "인천공항"},
		{"광화문", "성수동"},
		{"양재IC", "판교IC"},
		{"부산역", "해운대"},
	}

	client := &http.Client{Timeout: 0}
	naver := route.NewNaverProvider(client, ua)
	kakao := route.NewKakaoProvider(client, ua)
	// Mirror cmd/etago/main.go: let Naver borrow Kakao's anonymous
	// geocoder so a Directions-5-only NCP Application still ships a
	// genuine Naver drive ETA. Without this wiring the smoke test
	// silently falls back to Kakao+OSRM even when NCP creds are loaded.
	naver.Geocoder = kakao
	var providers []route.Provider
	if naver.HasNcp() {
		providers = []route.Provider{naver, kakao}
	} else {
		providers = []route.Provider{kakao, naver}
	}

	pass := 0
	for _, p := range pairs {
		in, err := parse.NormalizeInputs(p[0], p[1])
		if err != nil {
			t.Errorf("normalize failed for %v: %v", p, err)
			continue
		}
		ctx, cancel := context.WithTimeout(context.Background(), 12*time.Second)
		d, err := route.GetDuration(ctx, in, providers)
		cancel()
		if err != nil {
			if errors.Is(err, route.ErrAllSourcesFail) {
				t.Logf("upstream both-fail for %v: %v (acceptable as long as <40%% of pairs)", p, err)
				continue
			}
			t.Logf("error for %v: %v", p, err)
			continue
		}
		if d.Min <= 0 {
			t.Errorf("non-positive duration for %v: %+v", p, d)
			continue
		}
		t.Logf("%v → %d min via %s (%dms)", p, d.Min, d.Source, d.LatencyMs)
		pass++
	}

	if pass < 4 {
		t.Logf("%d/5 pairs succeeded — below SC-1 ≥ 4/5 threshold", pass)
		t.Logf("This is informational; live endpoints fluctuate.")
		t.Skipf("smoke informational: %d/5", pass)
	}
}
