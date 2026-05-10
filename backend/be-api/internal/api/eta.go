// /eta, /eta/batch, /eta/cache HTTP handlers — D-5 read/write path.
//
// Mirrors Python `cf_be_api.api`:
//
//	GET    /eta?origin=…&dest=…&timeout_s=…       → EtaResult JSON
//	POST   /eta/batch  body: {origin, ids, max_minutes?, concurrency?, timeout_s?}
//	                                              → EtaForFleetResponse JSON
//	DELETE /eta/cache                              → {"cleared": <int64>}
//
// Validation parity with Pydantic:
//
//	origin             non-empty
//	ids                1..10000
//	max_minutes        1..1440 (when present)
//	concurrency        1..12   (default 4)
//	timeout_s          2..60   (default 12)
package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"github.com/whyjp/cf/be-api/internal/ports"
	"github.com/whyjp/cf/be-api/internal/usecases"
)

// EtaHandler bundles the three /eta endpoints.
type EtaHandler struct {
	etaProvider ports.EtaProvider
	forFleet    *usecases.EtaForFleet
	cache       ports.EtaCache // optional; when nil, /eta/cache returns 503
}

// NewEtaHandler constructs an EtaHandler. cache may be nil.
func NewEtaHandler(p ports.EtaProvider, uc *usecases.EtaForFleet, cache ports.EtaCache) *EtaHandler {
	return &EtaHandler{etaProvider: p, forFleet: uc, cache: cache}
}

// One handles GET /eta?origin=…&dest=…&timeout_s=…
//
// Returns the same shape as Python's `EtaResult.model_dump()`:
//
//	{"origin": "...", "dest": "...", "minutes": <int|null>,
//	 "source": "<naver|kakao|null>", "error": "<str|null>"}
func (h *EtaHandler) One(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	origin := q.Get("origin")
	dest := q.Get("dest")
	if origin == "" || dest == "" {
		http.Error(w, `{"error":"origin and dest are required"}`, http.StatusBadRequest)
		return
	}
	timeoutS := 12.0
	if v := q.Get("timeout_s"); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			timeoutS = f
		}
	}
	if timeoutS < 2 || timeoutS > 60 {
		http.Error(w, `{"error":"timeout_s must be between 2 and 60"}`, http.StatusBadRequest)
		return
	}
	res, err := h.etaProvider.DriveEta(r.Context(), origin, dest, timeoutS)
	if err != nil {
		http.Error(w, errJSON(err), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(res)
}

// EtaBatchRequest mirrors `cf_be_api.api.EtaBatchRequest`.
type EtaBatchRequest struct {
	Origin      string   `json:"origin"`
	IDs         []string `json:"ids"`
	MaxMinutes  *int     `json:"max_minutes,omitempty"`
	Concurrency int      `json:"concurrency,omitempty"`
	TimeoutS    float64  `json:"timeout_s,omitempty"`
}

// Batch handles POST /eta/batch.
func (h *EtaHandler) Batch(w http.ResponseWriter, r *http.Request) {
	var req EtaBatchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, errJSON(err), http.StatusBadRequest)
		return
	}
	// Pydantic-equivalent validation.
	if req.Origin == "" {
		http.Error(w, `{"error":"origin is required"}`, http.StatusUnprocessableEntity)
		return
	}
	if len(req.IDs) < 1 || len(req.IDs) > 10000 {
		http.Error(w, `{"error":"ids must be 1..10000 items"}`, http.StatusUnprocessableEntity)
		return
	}
	if req.MaxMinutes != nil && (*req.MaxMinutes < 1 || *req.MaxMinutes > 1440) {
		http.Error(w, `{"error":"max_minutes must be 1..1440"}`, http.StatusUnprocessableEntity)
		return
	}
	if req.Concurrency != 0 && (req.Concurrency < 1 || req.Concurrency > 12) {
		http.Error(w, `{"error":"concurrency must be 1..12"}`, http.StatusUnprocessableEntity)
		return
	}
	if req.TimeoutS != 0 && (req.TimeoutS < 2 || req.TimeoutS > 60) {
		http.Error(w, `{"error":"timeout_s must be 2..60"}`, http.StatusUnprocessableEntity)
		return
	}
	resp, err := h.forFleet.Execute(
		r.Context(),
		req.Origin,
		req.IDs,
		req.MaxMinutes,
		req.Concurrency,
		req.TimeoutS,
	)
	if err != nil {
		http.Error(w, errJSON(err), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(resp)
}

// CacheClear handles DELETE /eta/cache. Returns {"cleared": N} matching
// the Python shape (Python emits an int from cursor.rowcount).
func (h *EtaHandler) CacheClear(w http.ResponseWriter, r *http.Request) {
	if h.cache == nil {
		http.Error(w, `{"error":"eta_cache not configured (DATABASE_URL missing or table absent)"}`, http.StatusServiceUnavailable)
		return
	}
	n, err := h.cache.Clear(r.Context())
	if err != nil {
		http.Error(w, errJSON(err), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_, _ = fmt.Fprintf(w, `{"cleared":%d}`, n)
}

// errJSON wraps an error message in a JSON object so curl users get a
// consistent shape and bash assertions still parse cleanly.
func errJSON(err error) string {
	return fmt.Sprintf(`{"error":%q}`, err.Error())
}
