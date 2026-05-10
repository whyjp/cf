//go:build regression
// +build regression

// Regression: assert Go endpoint responses are byte-equal (after sort_keys
// normalisation) to the Python be-api fixtures captured in fixtures/.
//
// Build with `go test -tags regression ./tests/regression/...`. Both servers
// must be reachable; only Go is hit at test time — the Python responses are
// frozen on disk under fixtures/ at the start of D-4 (so Python and Go are
// being compared against the same DB state and no drift creeps in if Python
// is later modified).
//
//	GO_BE_URL  default http://127.0.0.1:8073
//
// Run by hand after capturing fixtures:
//
//	mkdir -p tests/regression/fixtures
//	curl -s http://localhost:8071/facets > tests/regression/fixtures/facets.json
//	... (repeat for the other endpoints in the cases[] table) ...
//	go test -tags regression ./tests/regression/...
//
// Comparison strategy: parse both sides, recursively sort map keys, marshal
// back. This skips key-order accidents (Go's json package and FastAPI both
// preserve declaration order, but the sort makes the test resilient to the
// `concepts` field omitting `seed_term` etc.).
package regression

import (
	"encoding/json"
	"io"
	"net/http"
	"os"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func env(k, dflt string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return dflt
}

var goBase = env("GO_BE_URL", "http://127.0.0.1:8073")

// sortKeys recursively sorts map keys so json.Marshal emits a canonical form.
func sortKeys(v any) any {
	switch x := v.(type) {
	case map[string]any:
		out := make(map[string]any, len(x))
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			out[k] = sortKeys(x[k])
		}
		return out
	case []any:
		out := make([]any, len(x))
		for i, item := range x {
			out[i] = sortKeys(item)
		}
		return out
	}
	return v
}

// normalize parses then re-marshals with sorted keys.
func normalize(b []byte) (string, error) {
	var v any
	if err := json.Unmarshal(b, &v); err != nil {
		return "", err
	}
	out, err := json.Marshal(sortKeys(v))
	if err != nil {
		return "", err
	}
	return string(out), nil
}

func fetch(t *testing.T, path string) []byte {
	t.Helper()
	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Get(goBase + path)
	if err != nil {
		t.Fatalf("GET %s: %v", goBase+path, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("GET %s: status %d body %.200s", goBase+path, resp.StatusCode, string(body))
	}
	return body
}

func TestEndpoints_RegressionFixtures(t *testing.T) {
	cases := []struct {
		name, fixture, path string
	}{
		{"facets", "facets.json", "/facets"},
		{"concepts", "concepts.json", "/concepts"},
		{"themes", "themes.json", "/themes"},
		{"marks", "marks.json", "/marks"},
		{"featured_axes", "featured_axes.json", "/featured-axes"},
		{"concept_camps_valley", "concept_camps_valley.json", "/concepts/valley/camps?limit=20"},
		{"marks_management_camps", "marks_management_camps.json", "/marks/management/camps?limit=20"},
	}
	// detail fixture — discover dynamically so devs can re-capture against any sample id.
	files, _ := os.ReadDir("fixtures")
	for _, f := range files {
		n := f.Name()
		if strings.HasPrefix(n, "sites_detail_") && strings.HasSuffix(n, ".json") {
			id := strings.TrimSuffix(strings.TrimPrefix(n, "sites_detail_"), ".json")
			cases = append(cases, struct{ name, fixture, path string }{
				"sites_detail_" + id, n, "/sites/" + id,
			})
		}
	}

	for _, c := range cases {
		c := c
		t.Run(c.name, func(t *testing.T) {
			fixturePath := "fixtures/" + c.fixture
			expected, err := os.ReadFile(fixturePath)
			if err != nil {
				t.Skipf("fixture missing: %s (capture from Python first)", fixturePath)
			}
			actual := fetch(t, c.path)

			expNorm, err := normalize(expected)
			if err != nil {
				t.Fatalf("normalize fixture %s: %v", c.fixture, err)
			}
			actNorm, err := normalize(actual)
			if err != nil {
				t.Fatalf("normalize Go response %s: %v body=%.200s",
					c.path, err, string(actual))
			}
			assert.Equal(t, expNorm, actNorm, "endpoint: %s", c.path)
		})
	}
}
