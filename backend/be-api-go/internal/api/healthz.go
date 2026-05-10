package api

import (
	"encoding/json"
	"net/http"
)

// HealthzResponse is the JSON body returned from GET /healthz.
type HealthzResponse struct {
	Status string `json:"status"`
}

// Healthz reports liveness for the be-api Go service.
//
// D-1 scope is intentionally minimal — no DB / FalkorDB probing. Deeper
// readiness checks land alongside adapters in D-2.
func Healthz(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(HealthzResponse{Status: "ok"})
}
