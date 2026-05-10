package api

import (
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

// Handlers is the bundle of HTTP handlers wired by main. Each new endpoint
// adds a field; the wiring stays in main.go to keep the dependency graph
// explicit.
type Handlers struct {
	Sites *SitesHandler
}

// NewRouter wires the chi router with baseline middleware, the D-1 healthz
// endpoint, and (if provided) D-2+ domain endpoints.
//
// h may be nil — in that case only /healthz is exposed (used by the D-1
// integration test which doesn't have adapters configured).
func NewRouter(h *Handlers) *chi.Mux {
	r := chi.NewRouter()
	r.Use(middleware.Recoverer)
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Get("/healthz", Healthz)
	if h != nil && h.Sites != nil {
		r.Get("/sites", h.Sites.ServeHTTP)
	}
	return r
}
