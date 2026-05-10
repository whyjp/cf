"""Runtime settings — env override 가능 (TXCP_*)."""
from __future__ import annotations

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# default data_dir = <package>/../../../data == crawl/txcp/data (module-relative,
# robust to cwd). Mirrors camfit-crawl pattern.
_PKG_DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TXCP_", env_file=".env", extra="ignore")

    data_dir: Path = Field(default_factory=lambda: _PKG_DEFAULT_DATA)
    delay_min: float = 1.5
    delay_max: float = 3.0
    log_level: str = "INFO"
    max_pages_default: int = 600
    request_timeout_s: float = 20.0
    base_url: str = "https://m.thankqcamping.com"
