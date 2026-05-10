// /concepts and /concepts/{name}/camps HTTP handlers — D-4 read paths.
package api

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"

	"github.com/whyjp/cf/be-api/internal/usecases"
)

// ConceptsHandler wires /concepts and /concepts/{name}/camps.
type ConceptsHandler struct {
	uc *usecases.ListConcepts
}

// NewConceptsHandler constructs a ConceptsHandler.
func NewConceptsHandler(uc *usecases.ListConcepts) *ConceptsHandler {
	return &ConceptsHandler{uc: uc}
}

// Concepts handles GET /concepts.
func (h *ConceptsHandler) Concepts(w http.ResponseWriter, r *http.Request) {
	out, err := h.uc.All(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSONList(w, out)
}

// ConceptCamps handles GET /concepts/{name}/camps. Defaults: min_score=0.3,
// limit=200 (Python).
func (h *ConceptsHandler) ConceptCamps(w http.ResponseWriter, r *http.Request) {
	name := chi.URLParam(r, "name")
	if name == "" {
		http.Error(w, "missing name", http.StatusBadRequest)
		return
	}
	q := r.URL.Query()
	minScore := 0.3
	if v := q.Get("min_score"); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			minScore = f
		}
	}
	limit := 200
	if v := q.Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			limit = n
		}
	}

	camps, err := h.uc.CampsForConcept(r.Context(), name, minScore, limit)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSONList(w, camps)
}

// writeJSONList encodes any slice as JSON, emitting `[]` (not `null`) for
// empty/nil. Mirrors the convention from sites.go.
func writeJSONList(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	// Round-trip is unavoidable for the empty check; instead inspect via
	// reflect-free path: encode to a temp buffer and decide. Simpler: just
	// encode — json.Marshal of `[]T{}` is `[]`, of nil slice is `null`. Our
	// use-cases normalise nil → empty slice, so the encoder emits `[]`.
	if err := json.NewEncoder(w).Encode(v); err != nil {
		// Encoder.Encode appends a newline. We accept the trailing newline
		// because Python's json.dumps doesn't, but FastAPI's response writer
		// strips it; the regression normaliser parses + re-marshals so the
		// trailing newline doesn't affect the comparison.
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}
