// /sites/{site_id} HTTP handler — D-4 read path.
//
// 1:1 with the Python `cf_be_api.api.site_detail` handler:
//   * 200 + GetSiteDetail dict
//   * 404 with body `{"detail":"camp not found: <id>"}` if CampNotFound
package api

import (
	"encoding/json"
	"errors"
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/usecases"
)

// SiteDetailHandler wires /sites/{site_id} to the GetSiteDetail use-case.
type SiteDetailHandler struct {
	uc *usecases.GetSiteDetail
}

// NewSiteDetailHandler constructs a SiteDetailHandler.
func NewSiteDetailHandler(uc *usecases.GetSiteDetail) *SiteDetailHandler {
	return &SiteDetailHandler{uc: uc}
}

// SiteDetail handles GET /sites/{site_id}.
func (h *SiteDetailHandler) SiteDetail(w http.ResponseWriter, r *http.Request) {
	siteID := chi.URLParam(r, "site_id")
	if siteID == "" {
		http.Error(w, "missing site_id", http.StatusBadRequest)
		return
	}

	res, err := h.uc.Execute(r.Context(), siteID, 3) // top_reviews_n default = 3 (Python)
	if err != nil {
		var notFound *domain.CampNotFound
		if errors.As(err, &notFound) {
			writeFastAPIDetail(w, http.StatusNotFound, "camp not found: "+siteID)
			return
		}
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(res)
}

// writeFastAPIDetail writes a FastAPI-shaped error body: `{"detail": "..."}`.
//
// FastAPI's HTTPException(status, msg) responds with this exact body, and
// the regression fixtures (which would only exercise the 200 path) plus
// /sites/<bad-id> smoke tests will compare it. Keep the JSON shape stable.
func writeFastAPIDetail(w http.ResponseWriter, status int, detail string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"detail": detail})
}
