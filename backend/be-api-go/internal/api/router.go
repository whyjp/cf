package api

import (
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

// Handlers is the bundle of HTTP handlers wired by main. Each new endpoint
// adds a field; the wiring stays in main.go to keep the dependency graph
// explicit.
type Handlers struct {
	Sites  *SitesHandler  // D-2: GET /sites
	Search *SearchHandler // D-3: GET /sites/search, GET /sites/{site_id}/similar
}

// NewRouter wires the chi router with baseline middleware, the D-1 healthz
// endpoint, and (if provided) D-2+ domain endpoints.
//
// h may be nil — in that case only /healthz is exposed (used by the D-1
// integration test which doesn't have adapters configured).
//
// chi route precedence note: literal segments outrank wildcards on the same
// position, so /sites/search wins over /sites/{site_id}/similar. We register
// /sites/search BEFORE /sites/{site_id}/similar to make the priority
// explicit, but chi would route correctly either way.
func NewRouter(h *Handlers) *chi.Mux {
	r := chi.NewRouter()
	r.Use(middleware.Recoverer)
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Get("/healthz", Healthz)
	if h != nil && h.Sites != nil {
		r.Get("/sites", h.Sites.ServeHTTP)
	}
	if h != nil && h.Search != nil {
		r.Get("/sites/search", h.Search.SiteSearch)
		r.Get("/sites/{site_id}/similar", h.Search.SiteSimilar)
	}
	return r
}
