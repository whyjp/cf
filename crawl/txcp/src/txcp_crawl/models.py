"""캠핑장 레코드 모델 — camfit-puller 의 CampRecord 와 동형, txcp 필드 alias 추가."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import AliasChoices, BaseModel, Field, field_validator

KR_LAT_MIN, KR_LAT_MAX = 33.0, 39.0
KR_LON_MIN, KR_LON_MAX = 124.0, 132.0


class CampRecord(BaseModel):
    """단일 캠핑장 레코드. camfit-puller CampRecord 와 동형 + txcp 필드 alias.

    extra="allow": 사이트 응답 schema 변동 흡수 (CR-S2 대응).
    """

    model_config = {"extra": "allow", "populate_by_name": True}

    id: str = Field(
        validation_alias=AliasChoices("campSeq", "seq", "id"),
        min_length=1,
    )
    name: str = Field(
        validation_alias=AliasChoices("campName", "name"),
        min_length=1,
    )
    region_sido: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("sido", "region_sido"),
    )
    region_sigungu: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("sigungu", "region_sigungu"),
    )
    address: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("addr", "address"),
    )
    lat: Optional[float] = None
    lon: Optional[float] = None

    site_tp_codes: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("siteTps", "site_tp_codes"),
    )

    thumbnail: Optional[str] = None  # populated by adapter from campPicList[0].imgUrl
    min_basic_price: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("minBasicPrice", "min_basic_price"),
    )
    min_sale_price: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("minSalePrice", "min_sale_price"),
    )
    review_count: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("brdCnt", "review_count"),
    )
    monthly_review_count: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("monthlyBrdCnt", "monthly_review_count"),
    )

    source: str = "thankqcamping"
    pulled_at: Optional[datetime] = None

    @field_validator("id", mode="before")
    @classmethod
    def _id_to_str(cls, v):
        return str(v) if v is not None else v

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

    @field_validator("site_tp_codes", mode="before")
    @classmethod
    def _coerce_site_tps(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [c.strip() for c in v.split(",") if c.strip()]
        if isinstance(v, list):
            return [str(c) for c in v]
        return []

    def dedup_key(self) -> tuple[str, str]:
        """(source, id) — 후속 entity-resolution 까지 충돌 회피."""
        return (self.source, self.id)
