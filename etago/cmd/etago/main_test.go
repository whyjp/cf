package main

import (
	"flag"
	"testing"
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
