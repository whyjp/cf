package api

import (
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

// Handlers is the bundle of HTTP handlers wired by main. Each new endpoint
// adds a field; the wiring stays in main.go to keep the dependency graph
// explicit.
type Handlers struct {
	Sites      *SitesHandler      // D-2: GET /sites
	Search     *SearchHandler     // D-3: GET /sites/search, GET /sites/{site_id}/similar
	SiteDetail *SiteDetailHandler // D-4: GET /sites/{site_id}
	Facets     *FacetsHandler     // D-4: GET /facets
	Concepts   *ConceptsHandler   // D-4: GET /concepts, GET /concepts/{name}/camps
	Themes     *ThemesHandler     // D-4: GET /themes, GET /themes/{theme_id}/camps
	Marks      *MarksHandler      // D-4: GET /marks, GET /marks/{axis}/camps
	Eta        *EtaHandler        // D-5: GET /eta, POST /eta/batch, DELETE /eta/cache
	Admin      *AdminHandler      // D-6: POST /admin/{rebuild-graph,reembed}
	Graph      *GraphHandler      // D-6: GET /graph/{schema,sample,expand,search}
}

// NewRouter wires the chi router with baseline middleware, the D-1 healthz
// endpoint, and (if provided) D-2+ domain endpoints.
//
// h may be nil — in that case only /healthz is exposed (used by the D-1
// integration test which doesn't have adapters configured).
//
// chi route precedence: literal segments outrank wildcards on the same
// position, so /sites/search wins over /sites/{site_id}/similar. We register
// /sites/search BEFORE /sites/{site_id}/similar to make priority explicit;
// chi would route correctly either way.
//
// /sites/{site_id} (D-4) is registered AFTER /sites/search and
// /sites/{site_id}/similar so the more specific routes win at registration
// time too — an extra belt-and-braces.
func NewRouter(h *Handlers) *chi.Mux {
	r := chi.NewRouter()
	r.Use(middleware.Recoverer)
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Get("/healthz", Healthz)
	if h == nil {
		return r
	}

	// /featured-axes: pure constant — no use-case dependency, always wired.
	r.Get("/featured-axes", FeaturedAxes)

	if h.Facets != nil {
		r.Get("/facets", h.Facets.ServeHTTP)
	}
	if h.Sites != nil {
		r.Get("/sites", h.Sites.ServeHTTP)
	}
	if h.Search != nil {
		r.Get("/sites/search", h.Search.SiteSearch)
		r.Get("/sites/{site_id}/similar", h.Search.SiteSimilar)
	}
	if h.SiteDetail != nil {
		r.Get("/sites/{site_id}", h.SiteDetail.SiteDetail)
	}
	if h.Concepts != nil {
		r.Get("/concepts", h.Concepts.Concepts)
		r.Get("/concepts/{name}/camps", h.Concepts.ConceptCamps)
	}
	if h.Themes != nil {
		r.Get("/themes", h.Themes.Themes)
		r.Get("/themes/{theme_id}/camps", h.Themes.ThemeCamps)
	}
	if h.Marks != nil {
		r.Get("/marks", h.Marks.Marks)
		r.Get("/marks/{axis}/camps", h.Marks.AxisCamps)
	}
	if h.Eta != nil {
		r.Get("/eta", h.Eta.One)
		r.Post("/eta/batch", h.Eta.Batch)
		r.Delete("/eta/cache", h.Eta.CacheClear)
	}
	if h.Admin != nil {
		r.Post("/admin/rebuild-graph", h.Admin.AdminRebuildGraph)
		r.Post("/admin/reembed", h.Admin.AdminReembed)
	}
	if h.Graph != nil {
		r.Get("/graph/schema", h.Graph.GraphSchema)
		r.Get("/graph/sample", h.Graph.GraphSample)
		r.Get("/graph/expand", h.Graph.GraphExpand)
		r.Get("/graph/search", h.Graph.GraphSearch)
	}
	return r
}
