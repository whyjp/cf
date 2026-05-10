"""Pydantic-settings driven configuration. Env-prefix `CAMFIT_`.

Examples:
    CAMFIT_PG_DSN=postgresql://camfit:camfit@localhost:5432/camfit
    CAMFIT_VECTOR=pgvector
    CAMFIT_EMBEDDER=ko-sroberta
    CAMFIT_DATA_SOURCE=local-replay
    CAMFIT_GEOCODER=nominatim
    CAMFIT_ETA_PROVIDER=etago

A `.env` file at `D:/github/cf/.env` (or wherever pydantic-settings finds it) is
auto-loaded.
"""
from __future__ import annotations
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    pg_dsn: str = "postgresql://camfit:camfit@localhost:5432/camfit"
    pg_pool_min: int = 1
    pg_pool_max: int = 8

    falkor_host: str = "localhost"
    falkor_port: int = 6379
    falkor_graph: str = "camfit"

    embedder: Literal["ko-sroberta", "mock"] = "ko-sroberta"
    vector: Literal["pgvector", "numpy"] = "pgvector"
    # geo resolution lives in the etago binary (Naver NCP + Kakao K1 fallback).
    # `nominatim` is kept as a no-key fallback for offline/dev use.
    geocoder: Literal["etago", "nominatim", "mock"] = "etago"
    data_source: Literal["camfit", "local-replay", "mock"] = "local-replay"
    eta_provider: Literal["etago", "mock"] = "etago"

    # NOTE: post SP-A A1 directory move adds one level (backend/be-api/src/cf_be_api).
    # SP-B B4 dropped `fe_dir` here — be-api no longer serves static files;
    # the BFF (cf-be-for-fe) owns fe/dist/. data_dir kept for legacy parity.
    # parents[3] = backend/ (legacy data/ relative anchor).
    data_dir: Path = Path(__file__).resolve().parents[3] / "data"

    log_level: str = "INFO"

    # Theme/concept extraction tunables
    concept_top_k: int = 10
    concept_min_score: float = 0.3
    hdbscan_min_cluster_size: int = 8
    hdbscan_min_samples: int = 3

    model_config = SettingsConfigDict(
        env_prefix="CAMFIT_",
        env_file=".env",
        extra="ignore",
    )
