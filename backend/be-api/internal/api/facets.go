// /facets HTTP handler — D-4 read path.
//
// 1:1 with the Python `cf_be_api.api.facets` handler.
package api

import (
	"encoding/json"
	"net/http"

	"github.com/whyjp/cf/be-api/internal/usecases"
)

// FacetsHandler wires /facets to ListFacets.
type FacetsHandler struct {
	uc *usecases.ListFacets
}

// NewFacetsHandler constructs a FacetsHandler.
func NewFacetsHandler(uc *usecases.ListFacets) *FacetsHandler {
	return &FacetsHandler{uc: uc}
}

// ServeHTTP handles GET /facets.
func (h *FacetsHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	res, err := h.uc.Execute(r.Context())
	if err != nil {
		// Python falls back to an empty dict + X-Warning header on error;
		// for byte-equality with healthy-DB fixtures we instead surface 500
		// and let the regression test fail loudly. (Partial-failure mode is
		// out of scope for D-4; D-7 perf will revisit.)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(res)
}
