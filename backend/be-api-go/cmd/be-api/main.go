// be-api-go entrypoint. D-1 wired healthz; D-2 added postgres pool, CampReader,
// ListCamps, /sites; D-3 added the optional ONNX embedder + pgvector +
// semantic_search; D-4 wires the read-only sibling endpoints (/sites/{id},
// /facets, /concepts, /themes, /marks, /featured-axes).
//
// FalkorDB and JSONL source are constructed lazily — failing to connect to
// FalkorDB at boot does not block /sites since /sites doesn't depend on the
// graph. (D-6 admin/graph endpoints will require it.)
package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/whyjp/cf/be-api-go/internal/adapters/embed"
	"github.com/whyjp/cf/be-api-go/internal/adapters/eta"
	"github.com/whyjp/cf/be-api-go/internal/adapters/falkor"
	"github.com/whyjp/cf/be-api-go/internal/adapters/pgvector"
	"github.com/whyjp/cf/be-api-go/internal/adapters/postgres"
	"github.com/whyjp/cf/be-api-go/internal/api"
	"github.com/whyjp/cf/be-api-go/internal/settings"
	"github.com/whyjp/cf/be-api-go/internal/usecases"
)

func main() {
	cfg, err := settings.Load()
	if err != nil {
		slog.Error("config load", "err", err)
		os.Exit(1)
	}

	rootCtx, rootCancel := context.WithCancel(context.Background())
	defer rootCancel()

	// Postgres pool — fail fast if DSN is invalid, but keep going if the DB
	// is currently down (the pool will reconnect lazily).
	pool, err := postgres.NewPool(rootCtx, cfg.DatabaseURL)
	if err != nil {
		slog.Error("postgres pool", "err", err)
		os.Exit(1)
	}
	defer pool.Close()

	// D-2: CampReader → ListCamps → SitesHandler.
	campRepo := postgres.NewCampRepo(pool)
	listCamps := usecases.NewListCamps(campRepo)

	// D-4: Concept / Theme / Mark / Review / Facets readers.
	conceptRepo := postgres.NewConceptRepo(pool)
	themeRepo := postgres.NewThemeRepo(pool)
	markRepo := postgres.NewMarkRepo(pool)
	reviewRepo := postgres.NewReviewRepo(pool)
	facetsRepo := postgres.NewFacetsRepo(pool)

	getSiteDetail := usecases.NewGetSiteDetail(campRepo, reviewRepo, conceptRepo, themeRepo)
	listFacets := usecases.NewListFacets(facetsRepo, themeRepo)
	listConcepts := usecases.NewListConcepts(conceptRepo, campRepo)
	listThemes := usecases.NewListThemes(themeRepo, campRepo)
	listMarks := usecases.NewListMarks(markRepo)

	// D-5: ETA absorption — Naver NCP + Kakao K1 + OSRM in-process.
	// HTTP client with no built-in timeout; ctx drives cancellation per
	// provider attempt (PerSourceTimeout caps each individual call).
	etaHTTP := &http.Client{Timeout: 0}
	const etaUA = "cf-be-api-go/1.0 (+https://github.com/whyjp/cf)"
	naverProv := eta.NewNaverProvider(etaHTTP, etaUA, cfg.NaverNCPClientID, cfg.NaverNCPClientSecret)
	kakaoProv := eta.NewKakaoProvider(etaHTTP, etaUA)
	// Wire Kakao's K1 search as fallback geocoder when NCP only ships
	// Directions 5 (no Geocoding service) — same trick the etago CLI used.
	naverProv.Geocoder = kakaoProv
	// Chain order: Naver-NCP first when credentials are present (genuine
	// traffic-aware ETA from Naver Directions 5); otherwise Kakao+OSRM
	// first because anonymous Naver search is captcha-gated.
	var chain []eta.Provider
	if naverProv.HasNcp() {
		chain = []eta.Provider{naverProv, kakaoProv}
		slog.Info("eta chain: naver-ncp → kakao+osrm")
	} else {
		chain = []eta.Provider{kakaoProv, naverProv}
		slog.Info("eta chain: kakao+osrm → naver-anonymous (no NCP creds)")
	}
	etaProvider := eta.NewRouterProvider(chain)
	geocoder := eta.NewKakaoGeocoder(kakaoProv)
	etaForFleet := usecases.NewEtaForFleet(campRepo, etaProvider, geocoder)
	etaCacheRepo := postgres.NewEtaCacheRepo(pool)

	handlers := &api.Handlers{
		Sites:      api.NewSitesHandler(listCamps),
		SiteDetail: api.NewSiteDetailHandler(getSiteDetail),
		Facets:     api.NewFacetsHandler(listFacets),
		Concepts:   api.NewConceptsHandler(listConcepts),
		Themes:     api.NewThemesHandler(listThemes),
		Marks:      api.NewMarksHandler(listMarks),
		Eta:        api.NewEtaHandler(etaProvider, etaForFleet, etaCacheRepo),
	}

	// D-6: FalkorDB + /graph/* + /admin/*. FalkorDB connect failures are
	// non-fatal — /sites and friends keep working; only the graph endpoints
	// degrade. The admin endpoints additionally need the rebuild-graph
	// use-case (read repos + graph writer) and the reembed use-case (which
	// is wired only when the embedder + a vector upserter exist).
	graphRepo, err := falkor.NewGraphRepo(cfg.FalkorDBURL, "camfit")
	if err != nil {
		slog.Warn("falkor unavailable — /graph/* and /admin/rebuild-graph will return warnings", "err", err)
	} else {
		rebuildGraphUC := usecases.NewRebuildGraph(campRepo, conceptRepo, themeRepo, graphRepo)
		// reembed needs an Embedder + a VectorUpserter. The embedder is wired
		// further down (lazy ONNX); for D-6 we surface the endpoint with a
		// nil reembed so callers see 503 — D-7 will land the upserter.
		handlers.Admin = api.NewAdminHandler(rebuildGraphUC, nil)
		handlers.Graph = api.NewGraphHandler(graphRepo)
	}

	// D-3: optional semantic search wiring. ONNX assets are large (~423 MB)
	// and not always present in dev/CI; if any of the three paths is empty
	// we skip /sites/search and /sites/{id}/similar wiring so the rest of
	// the API stays usable. Failure to load with all three set is fatal.
	if cfg.OnnxLibPath != "" && cfg.OnnxModelPath != "" && cfg.OnnxTokenizerPath != "" {
		embedder, err := embed.NewOnnxEmbedder(
			cfg.OnnxLibPath, cfg.OnnxModelPath, cfg.OnnxTokenizerPath,
		)
		if err != nil {
			slog.Error("embed init", "err", err)
			os.Exit(1)
		}
		defer embedder.Close()

		vectorIdx := pgvector.NewIndex(pool)
		semantic := usecases.NewSemanticSearch(embedder, vectorIdx, campRepo)
		handlers.Search = api.NewSearchHandler(semantic)
		slog.Info("semantic search enabled",
			"model", cfg.OnnxModelPath,
			"tokenizer", cfg.OnnxTokenizerPath)
	} else {
		slog.Info("semantic search disabled (ONNX env vars unset)")
	}

	addr := cfg.Host + ":" + strconv.Itoa(cfg.Port)
	srv := &http.Server{
		Addr:         addr,
		Handler:      api.NewRouter(handlers),
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		slog.Info("be-api listening", "addr", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server", "err", err)
			os.Exit(1)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = srv.Shutdown(ctx)
}
