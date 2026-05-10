package route

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/whyjp/etago/internal/parse"
)

type stubProvider struct {
	name string
	d    Duration
	err  error
}

func (s stubProvider) Name() string { return s.name }
func (s stubProvider) Lookup(ctx context.Context, in parse.NormalizedInput) (Duration, error) {
	return s.d, s.err
}

func mkInput(t *testing.T) parse.NormalizedInput {
	t.Helper()
	in, err := parse.NormalizeInputs("강남역", "수원시청")
	if err != nil {
		t.Fatal(err)
	}
	return in
}

func TestRoute_naverWins_kakaoNeverCalled(t *testing.T) {
	naver := stubProvider{name: "naver", d: Duration{Min: 58, Source: "naver", LatencyMs: 200}}
	kakao := stubProvider{name: "kakao", err: errors.New("should not be called")}
	d, err := GetDuration(context.Background(), mkInput(t), []Provider{naver, kakao})
	if err != nil {
		t.Fatal(err)
	}
	if d.Source != "naver" || d.Min != 58 {
		t.Errorf("got %+v", d)
	}
}

func TestRoute_naverFails_fallsBackToKakao(t *testing.T) {
	naver := stubProvider{name: "naver", err: ErrUpstreamFail}
	kakao := stubProvider{name: "kakao", d: Duration{Min: 62, Source: "kakao"}}
	d, err := GetDuration(context.Background(), mkInput(t), []Provider{naver, kakao})
	if err != nil {
		t.Fatal(err)
	}
	if d.Source != "kakao" {
		t.Errorf("expected kakao fallback, got %+v", d)
	}
}

func TestRoute_naverInputRejected_noFallback(t *testing.T) {
	naver := stubProvider{name: "naver", err: ErrInputRejected}
	kakao := stubProvider{name: "kakao", d: Duration{Min: 99}}
	_, err := GetDuration(context.Background(), mkInput(t), []Provider{naver, kakao})
	if !errors.Is(err, ErrInputRejected) {
		t.Fatalf("want ErrInputRejected, got %v", err)
	}
}

func TestRoute_emptyPath_triggersFallback(t *testing.T) {
	naver := stubProvider{name: "naver", d: Duration{Min: 0, Source: "naver"}}
	kakao := stubProvider{name: "kakao", d: Duration{Min: 47, Source: "kakao"}}
	d, _ := GetDuration(context.Background(), mkInput(t), []Provider{naver, kakao})
	if d.Source != "kakao" {
		t.Errorf("expected kakao fallback on empty path, got %+v", d)
	}
}

func TestRoute_bothFail_returnsErrAllSourcesFail(t *testing.T) {
	naver := stubProvider{name: "naver", err: ErrUpstreamFail}
	kakao := stubProvider{name: "kakao", err: ErrUpstreamFail}
	_, err := GetDuration(context.Background(), mkInput(t), []Provider{naver, kakao})
	if !errors.Is(err, ErrAllSourcesFail) {
		t.Fatalf("want ErrAllSourcesFail, got %v", err)
	}
}

func TestRoute_perSourceTimeoutEnforced(t *testing.T) {
	slow := stubProviderFn(func(ctx context.Context) (Duration, error) {
		<-ctx.Done()
		return Duration{}, ctx.Err()
	})
	fast := stubProvider{name: "fast", d: Duration{Min: 10, Source: "fast"}}
	start := time.Now()
	d, err := GetDuration(context.Background(), mkInput(t), []Provider{slow, fast})
	if err != nil {
		t.Fatal(err)
	}
	if d.Source != "fast" {
		t.Errorf("expected fast provider after slow timeout, got %+v", d)
	}
	if elapsed := time.Since(start); elapsed > PerSourceTimeout+2*time.Second {
		t.Errorf("fallback took too long: %v", elapsed)
	}
}

type stubProviderFn func(ctx context.Context) (Duration, error)

func (f stubProviderFn) Name() string { return "slow" }
func (f stubProviderFn) Lookup(ctx context.Context, _ parse.NormalizedInput) (Duration, error) {
	return f(ctx)
}

func TestRoute_noProviders_returnsError(t *testing.T) {
	_, err := GetDuration(context.Background(), mkInput(t), nil)
	if err == nil {
		t.Fatal("expected error for empty provider list")
	}
}
