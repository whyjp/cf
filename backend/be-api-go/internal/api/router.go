package api

import (
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

// NewRouter wires the chi router with baseline middleware and the D-1
// healthz endpoint. Subsequent sprints (D-2~D-6) add domain endpoints.
func NewRouter() *chi.Mux {
	r := chi.NewRouter()
	r.Use(middleware.Recoverer)
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Get("/healthz", Healthz)
	return r
}
