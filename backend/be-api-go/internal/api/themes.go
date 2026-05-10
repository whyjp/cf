// /themes and /themes/{theme_id}/camps HTTP handlers — D-4 read paths.
package api

import (
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"

	"github.com/whyjp/cf/be-api-go/internal/usecases"
)

// ThemesHandler wires /themes and /themes/{theme_id}/camps.
type ThemesHandler struct {
	uc *usecases.ListThemes
}

// NewThemesHandler constructs a ThemesHandler.
func NewThemesHandler(uc *usecases.ListThemes) *ThemesHandler {
	return &ThemesHandler{uc: uc}
}

// Themes handles GET /themes.
func (h *ThemesHandler) Themes(w http.ResponseWriter, r *http.Request) {
	out, err := h.uc.All(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSONList(w, out)
}

// ThemeCamps handles GET /themes/{theme_id}/camps. Default: limit=200 (Python).
func (h *ThemesHandler) ThemeCamps(w http.ResponseWriter, r *http.Request) {
	themeID := chi.URLParam(r, "theme_id")
	if themeID == "" {
		http.Error(w, "missing theme_id", http.StatusBadRequest)
		return
	}
	limit := 200
	if v := r.URL.Query().Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			limit = n
		}
	}

	camps, err := h.uc.CampsForTheme(r.Context(), themeID, limit)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSONList(w, camps)
}
