// /marks and /marks/{axis}/camps HTTP handlers — D-4 read paths.
package api

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"

	"github.com/whyjp/cf/be-api/internal/usecases"
)

// MarksHandler wires /marks and /marks/{axis}/camps.
type MarksHandler struct {
	uc *usecases.ListMarks
}

// NewMarksHandler constructs a MarksHandler.
func NewMarksHandler(uc *usecases.ListMarks) *MarksHandler {
	return &MarksHandler{uc: uc}
}

// Marks handles GET /marks.
func (h *MarksHandler) Marks(w http.ResponseWriter, r *http.Request) {
	res, err := h.uc.Execute(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(res)
}

// AxisCamps handles GET /marks/{axis}/camps. Default: limit=100 (Python).
func (h *MarksHandler) AxisCamps(w http.ResponseWriter, r *http.Request) {
	axis := chi.URLParam(r, "axis")
	if axis == "" {
		http.Error(w, "missing axis", http.StatusBadRequest)
		return
	}
	q := r.URL.Query()
	var minLevel *string
	if v := q.Get("min_level"); v != "" {
		s := v
		minLevel = &s
	}
	limit := 100
	if v := q.Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			limit = n
		}
	}

	marks, err := h.uc.AxisCamps(r.Context(), axis, minLevel, limit)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSONList(w, marks)
}
