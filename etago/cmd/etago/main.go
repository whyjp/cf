// Command etago prints the recommended drive ETA between two natural-language
// place names by querying Korean public map services (Naver, with Kakao
// fallback). With --geocode it instead resolves a single Korean address to
// (lat, lon) using the same Naver-NCP-then-Kakao chain — the post-processing
// hook camfit-puller calls when assigning camp coordinates.
//
// Usage:
//
//	etago [flags] <start> <end>          # ETA mode (default)
//	etago --geocode [flags] <address>    # geocode mode
//
// Exit codes (UNIX BSD style):
//
//	0 success
//	1 unknown internal error (panic recovered)
//	2 input error (empty / coordinate / over-length / upstream 4xx)
//	3 external failure (every map source failed)
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"sync"
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
	geocode := fs.Bool("geocode", false, "geocode a single Korean address → (lat, lon) instead of ETA")
	batch := fs.Bool("batch", false, "with --geocode: read queries from stdin (one per line), emit NDJSON in input order")
	workers := fs.Int("workers", 6, "with --geocode --batch: parallel in-flight requests (Naver/Kakao have no native batch endpoint, this fans out per-query)")
	perTimeout := fs.Duration("per-timeout", 8*time.Second, "with --geocode --batch: per-query timeout (the global --timeout still caps the whole batch)")

	if err := fs.Parse(argv); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			return 0
		}
		return 2
	}

	client := &http.Client{Timeout: 0} // ctx drives cancellation, not Client.Timeout

	if *geocode {
		if *batch {
			// Batch ignores positional args; read from stdin.
			ctx, cancel := context.WithTimeout(context.Background(), *timeout)
			defer cancel()
			return runGeocodeBatch(ctx, *source, *ua, *workers, *perTimeout, *verbose, client, os.Stdin, stdout, stderr)
		}
		if fs.NArg() != 1 {
			printUsage(stderr)
			return 2
		}
		ctx, cancel := context.WithTimeout(context.Background(), *timeout)
		defer cancel()
		return runGeocode(ctx, fs.Arg(0), *source, *ua, *asJSON, *verbose, client, stdout, stderr)
	}

	if *batch {
		// --batch (without --geocode): drive-ETA batch. Stdin format =
		// one "origin\tdest" pair per line; output = NDJSON per pair, in
		// input order. Eliminates the per-pair process-spawn cost — one
		// subprocess fans N requests out internally.
		ctx, cancel := context.WithTimeout(context.Background(), *timeout)
		defer cancel()
		return runDriveBatch(ctx, *source, *ua, *workers, *perTimeout, *verbose, client, os.Stdin, stdout, stderr)
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

// runGeocode resolves `query` via the same Naver-NCP-first / Kakao-K1-fallback
// chain used by the ETA path. With --source we can force one engine; default
// `auto` prefers naver+ncp when credentials are present, kakao otherwise.
func runGeocode(
	ctx context.Context,
	query, source, ua string,
	asJSON, verbose bool,
	client *http.Client,
	stdout, stderr *os.File,
) int {
	naver := route.NewNaverProvider(client, ua)
	kakao := route.NewKakaoProvider(client, ua)
	naver.Geocoder = kakao // fallback for landmark / POI queries.

	type tryFn struct {
		name string
		fn   func() (float64, float64, error)
	}
	var chain []tryFn
	switch strings.ToLower(source) {
	case "naver":
		chain = []tryFn{{"naver", func() (float64, float64, error) { return naver.Geocode(ctx, query) }}}
	case "kakao":
		chain = []tryFn{{"kakao", func() (float64, float64, error) { return kakao.Geocode(ctx, query) }}}
	default: // auto
		if naver.HasNcp() {
			chain = []tryFn{
				{"naver", func() (float64, float64, error) { return naver.Geocode(ctx, query) }},
				{"kakao", func() (float64, float64, error) { return kakao.Geocode(ctx, query) }},
			}
		} else {
			chain = []tryFn{
				{"kakao", func() (float64, float64, error) { return kakao.Geocode(ctx, query) }},
				{"naver", func() (float64, float64, error) { return naver.Geocode(ctx, query) }},
			}
		}
	}

	var lastErr error
	for _, t := range chain {
		start := time.Now()
		lat, lng, err := t.fn()
		elapsed := time.Since(start)
		if verbose {
			if err != nil {
				fmt.Fprintf(stderr, "[%s] %dms err=%v\n", t.name, elapsed.Milliseconds(), err)
			} else {
				fmt.Fprintf(stderr, "[%s] %dms ok\n", t.name, elapsed.Milliseconds())
			}
		}
		if err == nil && (lat != 0 || lng != 0) {
			out := geocodeOutput(query, lat, lng, t.name, asJSON)
			fmt.Fprintln(stdout, out)
			return 0
		}
		if err != nil {
			lastErr = err
		}
	}
	if lastErr == nil {
		lastErr = fmt.Errorf("no result")
	}
	if errors.Is(lastErr, route.ErrInputRejected) {
		fmt.Fprintf(stderr, "etago: %v\n", lastErr)
		return 2
	}
	fmt.Fprintf(stderr, "etago: geocode failed: %v\n", lastErr)
	return 3
}

// runGeocodeBatch reads one query per line from stdin (`stdinR`), fans out N
// queries in parallel against the same provider chain runGeocode uses, and
// prints one NDJSON record per input line on stdout — in input order.
//
// Per-line output shape:
//
//	success: {"query":"…","lat":…,"lon":…,"source":"naver|kakao"}
//	failure: {"query":"…","error":"<short reason>"}
//
// We always emit a record (success or failure) per input line so the caller
// can pair input N with output N by ordinal. Exit 0 if any line succeeded;
// exit 3 only when every line failed AND we read at least one line. Stdin /
// stdout / stderr are passed in so tests can inject buffers; callers in
// main() pass os.Stdin/os.Stdout/os.Stderr.
func runGeocodeBatch(
	ctx context.Context,
	source, ua string,
	workers int,
	perTimeout time.Duration,
	verbose bool,
	client *http.Client,
	stdinR io.Reader,
	stdout, stderr io.Writer,
) int {
	naver := route.NewNaverProvider(client, ua)
	kakao := route.NewKakaoProvider(client, ua)
	naver.Geocoder = kakao

	type providerFn func(ctx context.Context, q string) (lat, lng float64, src string, err error)
	tryNaver := func(ctx context.Context, q string) (float64, float64, string, error) {
		lat, lng, err := naver.Geocode(ctx, q)
		return lat, lng, "naver", err
	}
	tryKakao := func(ctx context.Context, q string) (float64, float64, string, error) {
		lat, lng, err := kakao.Geocode(ctx, q)
		return lat, lng, "kakao", err
	}

	var chain []providerFn
	switch strings.ToLower(source) {
	case "naver":
		chain = []providerFn{tryNaver}
	case "kakao":
		chain = []providerFn{tryKakao}
	default: // auto
		if naver.HasNcp() {
			chain = []providerFn{tryNaver, tryKakao}
		} else {
			chain = []providerFn{tryKakao, tryNaver}
		}
	}

	if workers < 1 {
		workers = 1
	}

	// Read all queries up front. This bounds memory at "input size", which
	// is fine — even 100k addresses is sub-MB. It also lets us preserve
	// input order without juggling channels-with-indexes per worker.
	scanner := bufio.NewScanner(stdinR)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	var queries []string
	for scanner.Scan() {
		q := strings.TrimSpace(scanner.Text())
		queries = append(queries, q) // keep blanks too — they get an error record
	}
	if err := scanner.Err(); err != nil {
		fmt.Fprintf(stderr, "etago: stdin read: %v\n", err)
		return 2
	}

	type record struct {
		Query  string  `json:"query"`
		Lat    float64 `json:"lat,omitempty"`
		Lon    float64 `json:"lon,omitempty"`
		Source string  `json:"source,omitempty"`
		Error  string  `json:"error,omitempty"`
	}
	results := make([]record, len(queries))

	sem := make(chan struct{}, workers)
	var wg sync.WaitGroup
	var anyOK int32
	var okMu sync.Mutex
	startedAt := time.Now()

	for i, q := range queries {
		i, q := i, q
		if q == "" {
			results[i] = record{Query: q, Error: "empty"}
			continue
		}
		sem <- struct{}{}
		wg.Add(1)
		go func() {
			defer wg.Done()
			defer func() { <-sem }()

			itemCtx, cancel := context.WithTimeout(ctx, perTimeout)
			defer cancel()

			var lastErr error
			for _, p := range chain {
				lat, lng, src, err := p(itemCtx, q)
				if err == nil && (lat != 0 || lng != 0) {
					results[i] = record{Query: q, Lat: lat, Lon: lng, Source: src}
					okMu.Lock()
					anyOK = 1
					okMu.Unlock()
					return
				}
				lastErr = err
			}
			msg := "no result"
			if lastErr != nil {
				msg = lastErr.Error()
			}
			results[i] = record{Query: q, Error: shortErr(msg)}
		}()
	}
	wg.Wait()

	enc := json.NewEncoder(stdout)
	for _, r := range results {
		_ = enc.Encode(r)
	}
	if verbose {
		fmt.Fprintf(stderr, "[batch] %d queries, %dms total\n",
			len(queries), time.Since(startedAt).Milliseconds())
	}

	if len(queries) == 0 {
		// Nothing to do is success — caller asked us to process zero items.
		return 0
	}
	if anyOK == 1 {
		return 0
	}
	return 3
}

// runDriveBatch reads "origin\tdest" pairs from stdin (one per line), drives
// each through the same provider chain runDrive uses, and emits NDJSON in
// input order. Eliminates the per-pair process-spawn cost — one subprocess
// runs N requests in parallel via `workers` goroutines.
//
// Per-line output shape:
//
//	success: {"start":"…","end":"…","duration_min":N,"source":"naver|kakao|osrm"}
//	failure: {"start":"…","end":"…","error":"<short reason>"}
//
// Exit 0 if any line succeeded; exit 3 only when every line failed AND we
// read at least one line.
func runDriveBatch(
	ctx context.Context,
	source, ua string,
	workers int,
	perTimeout time.Duration,
	verbose bool,
	client *http.Client,
	stdinR io.Reader,
	stdout, stderr io.Writer,
) int {
	providers, err := buildProviders(source, ua, client)
	if err != nil {
		fmt.Fprintf(stderr, "etago: %v\n", err)
		return 2
	}
	if workers < 1 {
		workers = 1
	}

	type pair struct {
		Origin string
		Dest   string
	}
	scanner := bufio.NewScanner(stdinR)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	var pairs []pair
	for scanner.Scan() {
		line := scanner.Text()
		// Tab-separated origin\tdest. Lines without exactly one tab → error
		// record so caller can pair input N with output N by ordinal.
		parts := strings.SplitN(line, "\t", 2)
		if len(parts) == 2 {
			pairs = append(pairs, pair{
				Origin: strings.TrimSpace(parts[0]),
				Dest:   strings.TrimSpace(parts[1]),
			})
		} else {
			pairs = append(pairs, pair{Origin: strings.TrimSpace(line), Dest: ""})
		}
	}
	if err := scanner.Err(); err != nil {
		fmt.Fprintf(stderr, "etago: stdin read: %v\n", err)
		return 2
	}

	type record struct {
		Start       string `json:"start"`
		End         string `json:"end"`
		DurationMin int    `json:"duration_min,omitempty"`
		Source      string `json:"source,omitempty"`
		Error       string `json:"error,omitempty"`
	}
	results := make([]record, len(pairs))

	sem := make(chan struct{}, workers)
	var wg sync.WaitGroup
	var anyOK int32
	var okMu sync.Mutex
	startedAt := time.Now()

	for i, p := range pairs {
		i, p := i, p
		if p.Origin == "" || p.Dest == "" {
			results[i] = record{Start: p.Origin, End: p.Dest, Error: "empty"}
			continue
		}
		sem <- struct{}{}
		wg.Add(1)
		go func() {
			defer wg.Done()
			defer func() { <-sem }()

			itemCtx, cancel := context.WithTimeout(ctx, perTimeout)
			defer cancel()

			in, err := parse.NormalizeInputs(p.Origin, p.Dest)
			if err != nil {
				results[i] = record{Start: p.Origin, End: p.Dest, Error: shortErr(err.Error())}
				return
			}
			d, err := route.GetDuration(itemCtx, in, providers)
			if err != nil {
				results[i] = record{Start: p.Origin, End: p.Dest, Error: shortErr(err.Error())}
				return
			}
			results[i] = record{
				Start: p.Origin, End: p.Dest,
				DurationMin: d.Min,
				Source:      d.Source,
			}
			okMu.Lock()
			anyOK = 1
			okMu.Unlock()
		}()
	}
	wg.Wait()

	enc := json.NewEncoder(stdout)
	for _, r := range results {
		_ = enc.Encode(r)
	}
	if verbose {
		fmt.Fprintf(stderr, "[drive-batch] %d pairs, %dms total\n",
			len(pairs), time.Since(startedAt).Milliseconds())
	}

	if len(pairs) == 0 {
		return 0
	}
	if anyOK == 1 {
		return 0
	}
	return 3
}

func shortErr(msg string) string {
	const max = 200
	msg = strings.TrimSpace(msg)
	if len(msg) > max {
		return msg[:max]
	}
	return msg
}

func geocodeOutput(query string, lat, lng float64, source string, asJSON bool) string {
	if asJSON {
		b, _ := json.Marshal(map[string]any{
			"query":  query,
			"lat":    lat,
			"lon":    lng,
			"source": source,
		})
		return string(b)
	}
	return fmt.Sprintf("%.7f,%.7f", lat, lng)
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
	fmt.Fprintln(w, `etago — drive ETA + Korean address geocoder (Naver NCP + Kakao K1)

Usage:
  etago [flags] <start> <end>          # drive ETA between two place names
  etago --geocode [flags] <address>    # resolve address → "lat,lon" (or JSON)

Examples:
  etago "강남역" "수원시청"
  etago --json "서울역" "인천공항"
  etago --source kakao "양재IC" "판교IC"
  etago --geocode "강원 영월군 김삿갓면 내리계곡로 131-12"
  etago --geocode --json "충남 보령시 외산면 내성1길 117"
  cat addrs.txt | etago --geocode --batch --workers 8

Flags:
  --json              emit JSON instead of plain text
  --timeout duration  total timeout (default 12s)
  --verbose           log per-source latency to stderr
  --ua string         User-Agent override
  --source string     auto | naver | kakao   (default auto)
  --geocode           geocode a single Korean address instead of computing ETA
  --batch             with --geocode: read queries from stdin (one per line),
                      emit NDJSON in input order. Naver/Kakao have no native
                      batch API; this fans out per-query under one process.
  --workers int       with --geocode --batch: parallel in-flight requests (default 6)
  --per-timeout dur   with --geocode --batch: per-query timeout (default 8s)

Env (geocode mode prefers naver when set):
  NCP_CLIENT_ID, NCP_CLIENT_SECRET   Naver Cloud Platform Maps keys

Exit codes:
  0  success
  1  unknown / panic
  2  input error (empty, coordinate, over-length, 4xx)
  3  external failure (all map sources failed)`)
}
