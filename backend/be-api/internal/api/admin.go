// /admin/* — pipeline trigger endpoints (POST).
//
// 1:1 with Python `cf_be_api.api.rebuild_graph` and `reembed`. Both delegate
// to a use-case (`usecases.RebuildGraph` / `usecases.Reembed`); the handler
// itself is a thin transport adapter — execute, encode, return.
//
// These endpoints are administratively-gated (no auth here yet — same as the
// Python side; the deployment fronts them with VPN / CIDR allowlists). They
// are long-running and side-effecting; cross-validation against Python is
// skipped (response shape only — Python returns `{"camps_embedded": <N>}` for
// /reembed and a richer count map for /rebuild-graph).
package api

import (
	"context"
	"encoding/json"
	"net/http"
)

// RebuildGraphUseCase is the minimal interface AdminHandler depends on for
// /admin/rebuild-graph. Implemented by `usecases.RebuildGraph`.
type RebuildGraphUseCase interface {
	Execute(ctx context.Context) (map[string]int, error)
}

// ReembedUseCase is the minimal interface for /admin/reembed. Implemented by
// `usecases.Reembed` (returns the count of camps re-embedded).
type ReembedUseCase interface {
	Execute(ctx context.Context) (int, error)
}

// AdminHandler bundles /admin/{rebuild-graph,reembed}. Either field may be
// nil — when nil the corresponding endpoint returns 503.
type AdminHandler struct {
	Rebuild RebuildGraphUseCase
	Reembed ReembedUseCase
}

// NewAdminHandler constructs an AdminHandler.
func NewAdminHandler(rebuild RebuildGraphUseCase, reembed ReembedUseCase) *AdminHandler {
	return &AdminHandler{Rebuild: rebuild, Reembed: reembed}
}

// AdminRebuildGraph handles POST /admin/rebuild-graph.
//
// Returns the count map produced by the use-case (camps / concepts / themes /
// concept_edges / theme_edges) — same shape as Python.
func (h *AdminHandler) AdminRebuildGraph(w http.ResponseWriter, r *http.Request) {
	if h.Rebuild == nil {
		http.Error(w, `{"error":"rebuild_graph not configured"}`, http.StatusServiceUnavailable)
		return
	}
	out, err := h.Rebuild.Execute(r.Context())
	if err != nil {
		http.Error(w, errJSON(err), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(out)
}

// AdminReembed handles POST /admin/reembed.
//
// Returns `{"camps_embedded": N}` — same shape as Python.
func (h *AdminHandler) AdminReembed(w http.ResponseWriter, r *http.Request) {
	if h.Reembed == nil {
		http.Error(w, `{"error":"reembed not configured (ONNX or DB unset)"}`, http.StatusServiceUnavailable)
		return
	}
	n, err := h.Reembed.Execute(r.Context())
	if err != nil {
		http.Error(w, errJSON(err), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]int{"camps_embedded": n})
}
