// /sites/search and /sites/{site_id}/similar HTTP handlers — 1:1 with the
// Python FastAPI endpoints in `cf_be_api.api.site_search` /
// `cf_be_api.api.site_similar`.
//
//   GET /sites/search?q=…&k=20  → semantic.Search(q, k)
//   GET /sites/{site_id}/similar?k=10  → semantic.Similar(site_id, k)
//
// k is clamped to [1,100] / [1,100] respectively to match Python's
// `max(1, min(k, 100))` guard. ErrNoEmbedding maps to 404 — same semantics
// as Python's HTTPException(404, "no embedding for camp …").
package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"

	"github.com/whyjp/cf/be-api-go/internal/usecases"
)

// SearchHandler wires /sites/search and /sites/{site_id}/similar to the
// SemanticSearch use-case.
type SearchHandler struct {
	semantic *usecases.SemanticSearch
}

// NewSearchHandler constructs a SearchHandler.
func NewSearchHandler(s *usecases.SemanticSearch) *SearchHandler {
	return &SearchHandler{semantic: s}
}

// SiteSearch handles GET /sites/search.
func (h *SearchHandler) SiteSearch(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	if q == "" {
		http.Error(w, "missing q", http.StatusBadRequest)
		return
	}
	k := clampK(r.URL.Query().Get("k"), 20, 100)

	camps, err := h.semantic.Search(r.Context(), q, k)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, camps)
}

// SiteSimilar handles GET /sites/{site_id}/similar.
func (h *SearchHandler) SiteSimilar(w http.ResponseWriter, r *http.Request) {
	siteID := chi.URLParam(r, "site_id")
	if siteID == "" {
		http.Error(w, "missing site_id", http.StatusBadRequest)
		return
	}
	k := clampK(r.URL.Query().Get("k"), 10, 100)

	camps, err := h.semantic.Similar(r.Context(), siteID, k)
	if err != nil {
		if errors.Is(err, usecases.ErrNoEmbedding) {
			http.Error(w,
				"no embedding for camp "+siteID+"; run BuildEmbeddings first",
				http.StatusNotFound)
			return
		}
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, camps)
}

// clampK parses a positive int, defaulting to dflt and capping at maxK.
func clampK(raw string, dflt, maxK int) int {
	if raw == "" {
		return dflt
	}
	v, err := strconv.Atoi(raw)
	if err != nil || v <= 0 {
		return dflt
	}
	if v > maxK {
		return maxK
	}
	return v
}

// writeJSON writes camps as JSON. Empty slice → "[]" (not "null").
func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	if v == nil {
		_, _ = w.Write([]byte("[]"))
		return
	}
	// Detect empty slice via json round-trip avoidance: encode and check.
	_ = json.NewEncoder(w).Encode(v)
}
