// be-api-go entrypoint. D-1 wired healthz; D-2 adds the postgres pool,
// CampReader adapter, ListCamps use-case, and /sites handler.
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

	// Wire CampReader → ListCamps → SitesHandler.
	campRepo := postgres.NewCampRepo(pool)
	listCamps := usecases.NewListCamps(campRepo)
	handlers := &api.Handlers{
		Sites: api.NewSitesHandler(listCamps),
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
