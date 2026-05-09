from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class Region(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sido: str
    sigungu: str


class GeoPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=33.0, le=39.0)
    lon: float = Field(ge=124.0, le=132.0)


class Photo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    thumb_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class Camp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    region: Region
    address: Optional[str] = None
    geo: Optional[GeoPoint] = None
    types: list[str] = []
    facilities: list[str] = []
    additional_facilities: list[str] = []
    location_types: list[str] = []
    hashtags: list[str] = []
    collections: list[str] = []
    description: Optional[str] = None
    brief: Optional[str] = None
    location_brief: Optional[str] = None
    contact: Optional[str] = None
    price_start_from: Optional[int] = None
    price_end_to: Optional[int] = None
    num_of_reviews: int = 0
    num_of_viewed: int = 0
    bookmark_count: int = 0
    url: Optional[str] = None
    source: str = "camfit"
    photos: list[Photo] = []


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    camp_id: str
    user_nick: Optional[str] = None
    season: Optional[Literal["spring", "summer", "autumn", "winter"]] = None
    user_type: Optional[str] = None
    num_of_days: Optional[int] = None
    score: Optional[float] = None
    text: str
    is_clean: Optional[bool] = None
    is_kind: Optional[bool] = None
    is_manner: Optional[bool] = None
    is_convenient: Optional[bool] = None
    review_timestamp: Optional[int] = None
    medias: list[str] = []


class Concept(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    source: Literal["hashtag", "facility", "manual", "ngram"]
    category: Optional[str] = None
    description: Optional[str] = None
    is_axis: bool = False
    seed_term: Optional[str] = None


class CampConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")
    camp_id: str
    concept_id: str
    # Aggregated weighted-sum from camp_concept_aggregated view: 1.0×filter + 0.7×review + 0.5×desc.
    # Theoretical range [-2.2, +2.2] (all 3 sources, max signal). Sign indicates apply/negate.
    score: float = Field(ge=-3.0, le=3.0)


class Theme(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    centroid: Optional[list[float]] = None
    member_count: int = 0
    manual_label: Optional[str] = None


class EtaResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: str
    dest: str
    minutes: Optional[int] = None
    source: Optional[str] = None
    error: Optional[str] = None


class Mark(BaseModel):
    model_config = ConfigDict(extra="forbid")
    camp_id: str
    axis: str                                  # 'management' | 'view' | 'kids' | ...
    level: Literal["bib", "recommended", "notable", "exceptional"]
    score: float = Field(ge=-3.0, le=3.0)      # raw temperature-weighted score
    evidence: Optional[str] = None
