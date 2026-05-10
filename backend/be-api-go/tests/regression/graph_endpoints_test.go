//go:build regression
// +build regression

// Regression: assert /graph/* Go responses are byte-equal (after sort_keys
// normalisation) to the Python be-api fixtures captured in fixtures/.
//
// Capture Python fixtures with:
//
//	curl -s http://localhost:8071/graph/schema                              > fixtures/graph_schema.json
//	curl -s "http://localhost:8071/graph/sample?label=Camp&limit=5"         > fixtures/graph_sample_camp.json
//	curl -s "http://localhost:8071/graph/search?q=강원&label=Camp&limit=10"  > fixtures/graph_search_gangwon.json
//
// Then run:
//
//	go test -tags regression ./tests/regression/graph_endpoints_test.go -v
//
// Expand fixture is captured separately by extracting a node id from the
// sample response and querying /graph/expand?id=<id>.
//
// graph_sample uses the `labels` (plural) query param in Python — be sure to
// preserve the trailing s.
//
// Comparison strategy mirrors the existing endpoints_test.go: parse → recursive
// sort → marshal → string compare. The graph endpoints emit nested arrays of
// nodes whose internal `props` order may vary; the recursive-sort canonicalises.
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

// graphSortKeys recursively sorts map keys AND, for the top-level "nodes"
// array, sorts entries by their data.id so the array order is deterministic
// (Go map iteration is random; Python dict preserves insertion order — by
// sorting both sides we eliminate the difference).
func graphSortKeys(v any) any {
	switch x := v.(type) {
	case map[string]any:
		out := make(map[string]any, len(x))
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			out[k] = graphSortKeys(x[k])
		}
		return out
	case []any:
		out := make([]any, len(x))
		for i, item := range x {
			out[i] = graphSortKeys(item)
		}
		// If the slice contains node-like objects ({"data":{"id": ...}}),
		// sort by data.id so the comparison is order-insensitive. The
		// /graph/sample endpoint may return nodes in any order due to
		// FalkorDB result-set ordering being non-deterministic.
		sort.SliceStable(out, func(i, j int) bool {
			return nodeSortKey(out[i]) < nodeSortKey(out[j])
		})
		return out
	}
	return v
}

func nodeSortKey(v any) string {
	m, ok := v.(map[string]any)
	if !ok {
		return ""
	}
	data, ok := m["data"].(map[string]any)
	if !ok {
		return ""
	}
	id, _ := data["id"].(string)
	return id
}

func normalizeGraph(b []byte) (string, error) {
	var v any
	if err := json.Unmarshal(b, &v); err != nil {
		return "", err
	}
	out, err := json.Marshal(graphSortKeys(v))
	if err != nil {
		return "", err
	}
	return string(out), nil
}

func envGraph(k, dflt string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return dflt
}

func fetchGraph(t *testing.T, base, path string) []byte {
	t.Helper()
	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Get(base + path)
	if err != nil {
		t.Fatalf("GET %s: %v", base+path, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("GET %s: status %d body %.200s", base+path, resp.StatusCode, string(body))
	}
	return body
}

func TestGraphEndpoints_RegressionFixtures(t *testing.T) {
	base := envGraph("GO_BE_URL", "http://127.0.0.1:8073")
	cases := []struct {
		name, fixture, path string
	}{
		{"graph_schema", "graph_schema.json", "/graph/schema"},
		{"graph_sample_camp", "graph_sample_camp.json", "/graph/sample?labels=Camp&limit=5"},
		{"graph_search_gangwon", "graph_search_gangwon.json", "/graph/search?q=" + urlEncode("강원") + "&limit=10"},
		{"graph_expand", "graph_expand.json", ""}, // path resolved at test time from sample fixture
	}

	for _, c := range cases {
		c := c
		t.Run(c.name, func(t *testing.T) {
			fixturePath := "fixtures/" + c.fixture
			expected, err := os.ReadFile(fixturePath)
			if err != nil {
				t.Skipf("fixture missing: %s (capture from Python first)", fixturePath)
			}

			path := c.path
			if c.name == "graph_expand" {
				// Pull a node id from the captured sample fixture so we exercise
				// a real expand path. Skip if no node available.
				id := firstNodeIDFromSample(t)
				if id == "" {
					t.Skip("no node id in graph_sample_camp.json — skip expand")
				}
				path = "/graph/expand?id=" + urlEncode(id)
			}

			actual := fetchGraph(t, base, path)
			expNorm, err := normalizeGraph(expected)
			if err != nil {
				t.Fatalf("normalize fixture %s: %v", c.fixture, err)
			}
			actNorm, err := normalizeGraph(actual)
			if err != nil {
				t.Fatalf("normalize Go response %s: %v body=%.200s",
					path, err, string(actual))
			}
			assert.Equal(t, expNorm, actNorm, "endpoint: %s", path)
		})
	}
}

// firstNodeIDFromSample reads the captured sample fixture and returns the
// first node's data.id, or "" if no nodes / fixture missing.
func firstNodeIDFromSample(t *testing.T) string {
	t.Helper()
	b, err := os.ReadFile("fixtures/graph_sample_camp.json")
	if err != nil {
		return ""
	}
	var v map[string]any
	if err := json.Unmarshal(b, &v); err != nil {
		return ""
	}
	nodes, _ := v["nodes"].([]any)
	if len(nodes) == 0 {
		return ""
	}
	first, _ := nodes[0].(map[string]any)
	data, _ := first["data"].(map[string]any)
	id, _ := data["id"].(string)
	return id
}

// urlEncode percent-encodes a query value. Avoids importing net/url just to
// keep the test focused.
func urlEncode(s string) string {
	const hex = "0123456789ABCDEF"
	var b strings.Builder
	for _, c := range []byte(s) {
		switch {
		case ('a' <= c && c <= 'z') || ('A' <= c && c <= 'Z') || ('0' <= c && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~':
			b.WriteByte(c)
		default:
			b.WriteByte('%')
			b.WriteByte(hex[c>>4])
			b.WriteByte(hex[c&0x0F])
		}
	}
	return b.String()
}
