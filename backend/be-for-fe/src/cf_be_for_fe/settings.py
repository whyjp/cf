"""be-for-fe (BFF) settings.

Env-prefix `BFF_`. A `.env` at repo root is auto-loaded.

Examples:
    BFF_BE_API_BASE_URL=http://localhost:8071
    BFF_TIMEOUT_S=12.0
    BFF_ALLOWED_ORIGINS='["https://camfit.example.com"]'
    BFF_FE_DIR=/srv/cf/fe/dist
"""
from __future__ import annotations
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BFF_", env_file=".env", extra="ignore")

    be_api_base_url: str = "http://localhost:8071"
    timeout_s: float = 12.0
    allowed_origins: list[str] = ["*"]   # 프로덕션은 fe origin 화이트리스트로 좁힘

    # SP-B B4: BFF mounts fe/dist/ at "/". be-api no longer serves static.
    # Path layout: backend/be-for-fe/src/cf_be_for_fe/settings.py
    #   parents[4] = repo root (cf/) → fe/dist lives at <root>/fe/dist
    # If fe/dist doesn't exist (CI cold env, pre-build), the mount is skipped
    # at api.py — see the `is_dir()` guard there.
    fe_dir: Path = Path(__file__).resolve().parents[4] / "fe" / "dist"
