//go:build cross
// +build cross

// Cross-validation: Go /sites/search top-k overlap vs Python /sites/search.
//
// Per the D-3 SLA, the Go semantic search must agree with the Python
// reference on ≥ 95% of the top-10 IDs across a representative slice of
// Korean queries. This is a softer assertion than ListCamps (set equality)
// because semantic ranking has tiny float-quantization variance — pgvector
// HNSW + ONNX rounding can swap adjacent ranks.
//
// Build with `go test -tags cross ./tests/cross_validation/...`. Both servers
// must be reachable on PY_BE_URL (default :8071) and GO_BE_URL (default :8073).
package cross_validation

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// minOverlap is the per-query top-10 ID overlap floor (Spec D-3 = 0.95).
const minOverlap = 0.95

func fetchSearchIDs(t *testing.T, base, q string, k int) []string {
	t.Helper()
	u := base + "/sites/search?q=" + url.QueryEscape(q) + "&k=" + strconv.Itoa(k)
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Get(u)
	if err != nil {
		t.Fatalf("fetch %s: %v", u, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("fetch %s: status %d body %s", u, resp.StatusCode, string(body[:min(200, len(body))]))
	}
	var sites []siteLite
	if err := json.Unmarshal(body, &sites); err != nil {
		t.Fatalf("decode %s: %v body=%s", u, err, string(body[:min(200, len(body))]))
	}
	ids := make([]string, len(sites))
	for i, s := range sites {
		ids[i] = s.ID
	}
	return ids
}

// overlap returns |a ∩ b| / |b| (b is the reference / Python side).
func overlap(pyRef, goSet []string) float64 {
	if len(pyRef) == 0 {
		return 0
	}
	set := make(map[string]bool, len(goSet))
	for _, id := range goSet {
		set[id] = true
	}
	hit := 0
	for _, id := range pyRef {
		if set[id] {
			hit++
		}
	}
	return float64(hit) / float64(len(pyRef))
}

func TestSiteSearch_CrossValidate(t *testing.T) {
	queries := []string{"강원", "오토캠핑", "계곡 옆", "키즈", "글램핑"}
	for _, q := range queries {
		q := q
		t.Run(q, func(t *testing.T) {
			py := fetchSearchIDs(t, pyURL, q, 10)
			goIDs := fetchSearchIDs(t, goURL, q, 10)
			o := overlap(py, goIDs)
			t.Logf("q=%s py=%d go=%d overlap=%.3f", q, len(py), len(goIDs), o)
			assert.GreaterOrEqual(t, o, minOverlap,
				"top-10 overlap %.3f < %.2f for %q (py=%v go=%v)",
				o, minOverlap, q, py, goIDs)
		})
	}
}
