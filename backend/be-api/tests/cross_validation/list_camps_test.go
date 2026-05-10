//go:build cross
// +build cross

// Cross-validation: assert the Go /sites endpoint returns the same camp ID
// set as the Python /sites for a representative slice of query combinations.
//
// Build with `go test -tags cross ./tests/cross_validation/...`. Both servers
// must be reachable:
//
//	Python be-api on PY_BE_URL (default http://localhost:8071)
//	Go be-api on  GO_BE_URL (default http://127.0.0.1:8073)
//
// Byte-equal JSON parity is intentionally NOT asserted — that's D-4 once the
// projection layer settles. D-2 only commits to ID set equality.
package cross_validation

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"os"
	"sort"
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

var (
	pyURL = env("PY_BE_URL", "http://localhost:8071")
	goURL = env("GO_BE_URL", "http://127.0.0.1:8073")
)

type siteLite struct {
	ID string `json:"id"`
}

func fetchIDs(t *testing.T, base, path string) []string {
	t.Helper()
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Get(base + path)
	if err != nil {
		t.Fatalf("fetch %s: %v", base+path, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("fetch %s: status %d body %s", base+path, resp.StatusCode, string(body[:min(200, len(body))]))
	}
	var sites []siteLite
	if err := json.Unmarshal(body, &sites); err != nil {
		t.Fatalf("decode %s: %v body=%s", base+path, err, string(body[:min(200, len(body))]))
	}
	ids := make([]string, len(sites))
	for i, s := range sites {
		ids[i] = s.ID
	}
	sort.Strings(ids)
	return ids
}

// q builds /sites?...=... with URL-encoded values. Python gunicorn rejects
// raw multibyte bytes, so encoding is mandatory.
func q(pairs ...[2]string) string {
	v := url.Values{}
	for _, p := range pairs {
		v.Add(p[0], p[1])
	}
	if len(v) == 0 {
		return "/sites"
	}
	return "/sites?" + v.Encode()
}

func TestListCamps_CrossValidate(t *testing.T) {
	// NOTE: `region + concept` combo is intentionally NOT in the parity
	// suite. The Python adapter has a latent positional-placeholder bug:
	// it builds `... JOIN ... AND agg_0.concept_id=%s WHERE c.sido=%s` but
	// appends params in WHERE-first order ([sido, concept]), so psycopg
	// binds sido='강원' to concept_id and concept='valley' to sido — the
	// query then returns 0 for any region+concept pair. Go uses numbered
	// $-placeholders (`bind()` in camp_repo.go) and binds correctly,
	// returning the expected ~46 강원+valley camps. Including this case
	// would assert Go reproduces Python's bug — the opposite of what we
	// want. D-4 fixture diff will surface this as a `find` for the user.
	cases := []struct {
		name, path string
	}{
		{"all", "/sites"},
		{"limit_5", q([2]string{"limit", "5"})},
		{"region_gangwon", q([2]string{"region", "강원"})},
		{"region_gyeonggi", q([2]string{"region", "경기"})},
		{"region_jeju", q([2]string{"region", "제주"})},
		{"sigungu", q([2]string{"sigungu", "가평군"})},
		{"concept_valley", q([2]string{"concept", "valley"})},
		{"concept_kids", q([2]string{"concept", "kids"})},
		{"concepts_any", q([2]string{"concepts_any", "valley,kids"})},
		{"concepts_multi_AND", q([2]string{"concept", "valley"}, [2]string{"concept", "autumn"})},
	}
	for _, c := range cases {
		c := c
		t.Run(c.name, func(t *testing.T) {
			py := fetchIDs(t, pyURL, c.path)
			goIDs := fetchIDs(t, goURL, c.path)
			assert.Equal(t, py, goIDs,
				"%s — Python(%d) and Go(%d) IDs differ", c.name, len(py), len(goIDs))
		})
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
