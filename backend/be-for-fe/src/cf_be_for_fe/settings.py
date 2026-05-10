"""be-for-fe (BFF) settings.

Env-prefix `BFF_`. A `.env` at repo root is auto-loaded.

Examples:
    BFF_BE_API_BASE_URL=http://localhost:8071
    BFF_TIMEOUT_S=12.0
    BFF_ALLOWED_ORIGINS='["https://camfit.example.com"]'
"""
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BFF_", env_file=".env", extra="ignore")

    be_api_base_url: str = "http://localhost:8071"
    timeout_s: float = 12.0
    allowed_origins: list[str] = ["*"]   # 프로덕션은 fe origin 화이트리스트로 좁힘
