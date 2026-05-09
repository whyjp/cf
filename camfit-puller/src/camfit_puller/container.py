"""Composition root — wires concrete adapters to use-cases.

Lifetime: typically one Container per process (FastAPI app or CLI invocation).
The container holds long-lived adapters (PG pool, embedder model) and exposes
factory methods that return new use-case instances per request.

Lazy initialization: heavy adapters (the embedder which loads ~400MB) are only
instantiated when first accessed via property. Settings drives all selection.
"""
from __future__ import annotations
from functools import cached_property
from pathlib import Path
from typing import Optional

from .settings import Settings

# Adapters
from .adapters.postgres.pool import PostgresPool
from .adapters.postgres.camp_repo import PostgresCampReader, PostgresCampWriter
from .adapters.postgres.review_repo import PostgresReviewReader, PostgresReviewWriter
from .adapters.postgres.concept_repo import PostgresConceptRepo
from .adapters.postgres.theme_repo import PostgresThemeRepo
from .adapters.postgres.filter_repo import PostgresCamfitFilterRepo
from .adapters.postgres.mapping_repo import PostgresFilterConceptMappingRepo
from .adapters.postgres.signal_repos import (
    PostgresFilterSignalWriter,
    PostgresDescSignalWriter,
    PostgresReviewSignalWriter,
)
from .adapters.postgres.geocode_cache_repo import PostgresGeocodeCacheRepo
from .adapters.postgres.eta_cache_repo import PostgresEtaCacheRepo
from .adapters.postgres.mark_repo import PostgresMarkRepo
from .adapters.pgvector.index import PgvectorIndex
from .adapters.falkor.graph import FalkorGraph
from .adapters.cluster.hdbscan import HdbscanClusterer
from .adapters.extract.keybert import KeyBertExtractor
from .adapters.extract.negation import HeuristicNegationExtractor

# Use-cases
from .usecases.ingest_snapshot import IngestSnapshot
from .usecases.geocode_pending import GeocodePending
from .usecases.build_vocabulary import BuildVocabulary
from .usecases.build_embeddings import BuildEmbeddings
from .usecases.extract_filter_signals import ExtractCamfitFilterSignals
from .usecases.extract_desc_signals import ExtractDescSignals
from .usecases.extract_review_signals import ExtractReviewSignals
from .usecases.refresh_aggregated import RefreshAggregatedSignals
from .usecases.discover_themes import DiscoverThemes
from .usecases.rebuild_graph import RebuildGraph
from .usecases.semantic_search import SemanticSearch
from .usecases.get_site_detail import GetSiteDetail
from .usecases.eta_for_fleet import EtaForFleet
from .usecases.compute_marks import ComputeMarks


class Container:
    """Holds long-lived adapters; supplies use-case factories.

    Heavy adapters are wrapped in @cached_property so they're only loaded on
    first use (e.g. embedder loads ~400MB).
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        # PG pool: cheap; eager.
        self._pg = PostgresPool(
            settings.pg_dsn,
            min_size=settings.pg_pool_min,
            max_size=settings.pg_pool_max,
        )

    # ──────────────── Storage adapters (eager — cheap) ───────────────────
    @cached_property
    def camps_read(self) -> PostgresCampReader:
        return PostgresCampReader(self._pg)

    @cached_property
    def camps_write(self) -> PostgresCampWriter:
        return PostgresCampWriter(self._pg)

    @cached_property
    def reviews_read(self) -> PostgresReviewReader:
        return PostgresReviewReader(self._pg)

    @cached_property
    def reviews_write(self) -> PostgresReviewWriter:
        return PostgresReviewWriter(self._pg)

    @cached_property
    def concept_repo(self) -> PostgresConceptRepo:
        return PostgresConceptRepo(self._pg)

    @cached_property
    def theme_repo(self) -> PostgresThemeRepo:
        return PostgresThemeRepo(self._pg)

    @cached_property
    def filter_repo(self) -> PostgresCamfitFilterRepo:
        return PostgresCamfitFilterRepo(self._pg)

    @cached_property
    def mapping_repo(self) -> PostgresFilterConceptMappingRepo:
        return PostgresFilterConceptMappingRepo(self._pg)

    @cached_property
    def filter_signal_writer(self) -> PostgresFilterSignalWriter:
        return PostgresFilterSignalWriter(self._pg)

    @cached_property
    def desc_signal_writer(self) -> PostgresDescSignalWriter:
        return PostgresDescSignalWriter(self._pg)

    @cached_property
    def review_signal_writer(self) -> PostgresReviewSignalWriter:
        return PostgresReviewSignalWriter(self._pg)

    @cached_property
    def geocode_cache(self) -> PostgresGeocodeCacheRepo:
        return PostgresGeocodeCacheRepo(self._pg)

    @cached_property
    def eta_cache(self) -> PostgresEtaCacheRepo:
        return PostgresEtaCacheRepo(self._pg)

    @cached_property
    def mark_repo(self) -> PostgresMarkRepo:
        return PostgresMarkRepo(self._pg)

    # ──────────────── Vector / Graph (lazy — needs network) ──────────────
    @cached_property
    def vector(self):
        if self.settings.vector == "numpy":
            from .adapters.numpy_vector.index import NumpyVectorIndex
            return NumpyVectorIndex(dim=768, model_name=self.settings.embedder)
        # default: pgvector
        return PgvectorIndex(self._pg, dim=768, model_name=self.settings.embedder)

    @cached_property
    def graph(self) -> FalkorGraph:
        return FalkorGraph(
            host=self.settings.falkor_host,
            port=self.settings.falkor_port,
            graph=self.settings.falkor_graph,
        )

    # ──────────────── Heavy adapters (lazy — one-shot warmup) ─────────────
    @cached_property
    def embedder(self):
        if self.settings.embedder == "mock":
            from .adapters.embed.mock import MockEmbedder
            return MockEmbedder()
        # default: ko-sroberta
        from .adapters.embed.sentence_transformers import KoSrobertaEmbedder
        return KoSrobertaEmbedder()

    @cached_property
    def geocoder(self):
        if self.settings.geocoder == "mock":
            from .adapters.geocode.mock import MockGeocoder
            return MockGeocoder()
        from .adapters.geocode.nominatim import NominatimGeocoder
        from .adapters.geocode.cached import CachedGeocoder
        return CachedGeocoder(NominatimGeocoder(), self.geocode_cache)

    @cached_property
    def eta(self):
        if self.settings.eta_provider == "mock":
            from .adapters.eta.mock import MockEtaProvider
            return MockEtaProvider()
        from .adapters.eta.etago_subprocess import EtagoSubprocessProvider
        return EtagoSubprocessProvider()

    @cached_property
    def source(self):
        if self.settings.data_source == "mock":
            # Mock source not provided in T22; for now accept this as NotImplemented.
            raise NotImplementedError("data_source=mock not yet implemented")
        if self.settings.data_source == "camfit":
            # CamfitSource (CloakBrowser-driven) lives outside this task's scope —
            # T22 only created LocalReplaySource. CamfitSource is for live fetch.
            # Defer to LocalReplaySource which is the canonical input for ETL.
            from .adapters.source.local_replay import LocalReplaySource
            return LocalReplaySource(self.settings.data_dir)
        # default: local-replay
        from .adapters.source.local_replay import LocalReplaySource
        return LocalReplaySource(self.settings.data_dir)

    @cached_property
    def concept_extractor(self) -> KeyBertExtractor:
        return KeyBertExtractor(self.embedder, self.concept_repo)

    @cached_property
    def negation_extractor(self) -> HeuristicNegationExtractor:
        return HeuristicNegationExtractor(self.concept_repo)

    @cached_property
    def theme_clusterer(self) -> HdbscanClusterer:
        return HdbscanClusterer(
            min_cluster_size=self.settings.hdbscan_min_cluster_size,
            min_samples=self.settings.hdbscan_min_samples,
        )

    # ──────────────── Use-case factories ─────────────────────────────────
    def ingest_snapshot(self) -> IngestSnapshot:
        return IngestSnapshot(self.source, self.camps_write, self.reviews_write, self.filter_repo)

    def geocode_pending(self) -> GeocodePending:
        return GeocodePending(self.camps_read, self.camps_write, self.geocoder)

    def build_vocabulary(self) -> BuildVocabulary:
        return BuildVocabulary(self.camps_read, self.concept_repo)

    def build_embeddings(self) -> BuildEmbeddings:
        return BuildEmbeddings(
            self.camps_read, self.reviews_read, self.embedder, self.vector,
        )

    def extract_filter_signals(self) -> ExtractCamfitFilterSignals:
        return ExtractCamfitFilterSignals(
            self.camps_read, self.mapping_repo, self.filter_signal_writer,
        )

    def extract_desc_signals(self) -> ExtractDescSignals:
        return ExtractDescSignals(
            self.camps_read, self.reviews_read, self.embedder,
            self.concept_extractor, self.desc_signal_writer,
        )

    def extract_review_signals(self) -> ExtractReviewSignals:
        return ExtractReviewSignals(
            self.reviews_read, self.negation_extractor, self.review_signal_writer,
        )

    def refresh_aggregated(self) -> RefreshAggregatedSignals:
        return RefreshAggregatedSignals(self._pg)

    def discover_themes(self) -> DiscoverThemes:
        return DiscoverThemes(
            self.camps_read, self.vector, self.theme_clusterer,
            self.theme_repo, self.concept_repo,
        )

    def rebuild_graph(self) -> RebuildGraph:
        return RebuildGraph(self.camps_read, self.concept_repo, self.theme_repo, self.graph)

    def semantic_search(self) -> SemanticSearch:
        return SemanticSearch(self.embedder, self.vector, self.camps_read)

    def get_site_detail(self) -> GetSiteDetail:
        return GetSiteDetail(
            self.camps_read, self.reviews_read, self.concept_repo, self.theme_repo,
        )

    def eta_for_fleet(self) -> EtaForFleet:
        return EtaForFleet(self.camps_read, self.eta)

    def compute_marks(self) -> ComputeMarks:
        return ComputeMarks(self._pg, self.mark_repo)

    def close(self) -> None:
        self._pg.close()
