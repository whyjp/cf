from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, field_validator


KR_LAT_MIN, KR_LAT_MAX = 33.0, 39.0
KR_LON_MIN, KR_LON_MAX = 124.0, 132.0


class CampRecord(BaseModel):
    """Single campsite record. Keep extra fields permissive — camfit 스키마 변동 흡수."""

    model_config = {"extra": "allow"}

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    url: Optional[str] = None
    region_sido: Optional[str] = None
    region_sigungu: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    categories: list[str] = Field(default_factory=list)
    facilities: list[str] = Field(default_factory=list)
    has_valley: Optional[bool] = None
    has_kids: Optional[bool] = None
    has_trampoline: Optional[bool] = None
    description: Optional[str] = None
    raw_image_url: Optional[str] = None

    @field_validator("lat")
    @classmethod
    def _lat_in_kr_or_none(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if not (KR_LAT_MIN <= v <= KR_LAT_MAX):
            return None
        return v

    @field_validator("lon")
    @classmethod
    def _lon_in_kr_or_none(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if not (KR_LON_MIN <= v <= KR_LON_MAX):
            return None
        return v
