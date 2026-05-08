// Command etago prints the recommended drive ETA between two natural-language
// place names by querying Korean public map services (Naver, with Kakao
// fallback). It uses no API keys, no login, and no persistent cookies.
//
// Usage:
//
//	etago [flags] <start> <end>
//
// Exit codes (UNIX BSD style):
//
//	0 success
//	1 unknown internal error (panic recovered)
//	2 input error (empty / coordinate / over-length / upstream 4xx)
//	3 external failure (every map source failed)
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/whyjp/etago/internal/duration"
	"github.com/whyjp/etago/internal/envfile"
	"github.com/whyjp/etago/internal/parse"
	"github.com/whyjp/etago/internal/route"
)

const defaultUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
	"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

func main() {
	// Load .env from cwd (or up to 5 parent dirs) before reading flags
	// so NaverProvider can pick up NCP_CLIENT_ID / NCP_CLIENT_SECRET on
	// construction. A missing .env is silently fine.
	_ = envfile.LoadDefault()
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(argv []string, stdout, stderr *os.File) (code int) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Fprintf(stderr, "etago: panic: %v\n", r)
			code = 1
		}
	}()

	fs := flag.NewFlagSet("etago", flag.ContinueOnError)
	fs.SetOutput(stderr)
	fs.Usage = func() { printUsage(stderr) }

	asJSON := fs.Bool("json", false, "emit JSON instead of '<min> min'")
	timeout := fs.Duration("timeout", 12*time.Second, "total timeout (covers both providers)")
	verbose := fs.Bool("verbose", false, "log per-source latency to stderr")
	ua := fs.String("ua", defaultUA, "User-Agent override")
	source := fs.String("source", "auto", "auto | naver | kakao")

	if err := fs.Parse(argv); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			return 0
		}
		return 2
	}
	if fs.NArg() != 2 {
		printUsage(stderr)
		return 2
	}

	in, err := parse.NormalizeInputs(fs.Arg(0), fs.Arg(1))
	if err != nil {
		fmt.Fprintf(stderr, "etago: %v\n", err)
		return 2
	}

	client := &http.Client{Timeout: 0} // ctx drives cancellation, not Client.Timeout
	providers, err := buildProviders(*source, *ua, client)
	if err != nil {
		fmt.Fprintf(stderr, "etago: %v\n", err)
		return 2
	}

	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()

	d, err := route.GetDuration(ctx, in, providers)
	if err != nil {
		switch {
		case errors.Is(err, route.ErrInputRejected):
			fmt.Fprintf(stderr, "etago: %v\n", err)
			return 2
		default:
			fmt.Fprintf(stderr, "etago: %v\n", err)
			return 3
		}
	}

	if *verbose {
		fmt.Fprintf(stderr, "[%s] %dms\n", d.Source, d.LatencyMs)
	}
	fmt.Fprintln(stdout, duration.Format(d, in, duration.Options{JSON: *asJSON}))
	return 0
}

func buildProviders(source, ua string, client *http.Client) ([]route.Provider, error) {
	naver := route.NewNaverProvider(client, ua)
	kakao := route.NewKakaoProvider(client, ua)
	// Wire Kakao's anonymous geocoder into Naver so the NCP path can
	// resolve coordinates even when the NCP Application has only
	// Directions 5 enabled (the common cheap setup).
	naver.Geocoder = kakao
	switch strings.ToLower(source) {
	case "auto", "":
		// With NCP credentials present, Naver returns the genuine
		// Naver Map traffic-aware ETA — put it first. Without
		// credentials, Naver's anonymous search is captcha-gated
		// and almost always fails, so Kakao+OSRM goes first and
		// Naver sits behind as a structural fallback.
		if naver.HasNcp() {
			return []route.Provider{naver, kakao}, nil
		}
		return []route.Provider{kakao, naver}, nil
	case "naver":
		return []route.Provider{naver}, nil
	case "kakao":
		return []route.Provider{kakao}, nil
	default:
		return nil, fmt.Errorf("unknown --source %q (auto|naver|kakao)", source)
	}
}

func printUsage(w *os.File) {
	fmt.Fprintln(w, `etago — drive ETA between two place names (no API key, no login)

Usage:
  etago [flags] <start> <end>

Examples:
  etago "강남역" "수원시청"
  etago --json "서울역" "인천공항"
  etago --source kakao "양재IC" "판교IC"
  etago --verbose "광화문" "성수동"

Flags:
  --json              emit JSON instead of "<min> min"
  --timeout duration  total timeout (default 12s)
  --verbose           log per-source latency to stderr
  --ua string         User-Agent override
  --source string     auto | naver | kakao   (default auto)

Exit codes:
  0  success
  1  unknown / panic
  2  input error (empty, coordinate, over-length, 4xx)
  3  external failure (all map sources failed)`)
}
