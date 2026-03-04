"""Shared Pydantic v2 schemas for RentRadar API."""

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")


# ── Listings ──────────────────────────────────────────────────────────


class ListingBase(BaseModel):
    address: str
    unit: str | None = None
    borough: str
    neighborhood: str | None = None
    price: int = Field(gt=0)
    bedrooms: int = Field(ge=0)
    bathrooms: float = Field(ge=0)
    sqft: int | None = Field(default=None, gt=0)
    amenities: list[str] = Field(default_factory=list)
    description: str | None = None


class ListingCreate(ListingBase):
    source: str
    source_url: str
    raw_data: dict = Field(default_factory=dict)


class ListingSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    source_url: str
    scraped_at: datetime


class PriceHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    price: int
    previous_price: int | None = None
    event_type: str
    recorded_at: datetime


class ListingResponse(ListingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lat: float | None = None
    lng: float | None = None
    undervalue_score: float | None = None
    rs_probability: float | None = None
    quality_score: float | None = None
    canonical_hash: str
    status: str
    source_count: int
    days_on_market: int | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    sources: list[ListingSourceResponse] = Field(default_factory=list)


class ListingDetailResponse(ListingResponse):
    """Extended listing with price history and RS info."""

    price_history: list[PriceHistoryResponse] = Field(default_factory=list)
    rs_nearby: bool = False


# ── Filters ───────────────────────────────────────────────────────────


class ListingFilters(BaseModel):
    min_price: int | None = None
    max_price: int | None = None
    bedrooms: int | None = None
    borough: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_miles: float | None = Field(default=None, gt=0)
    amenities: list[str] | None = None
    min_score: float | None = Field(default=None, ge=0, le=1)
    sort_by: str = "created_at"
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


# ── Users ─────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ── Saved Searches ───────────────────────────────────────────────────


class SavedSearchCreate(BaseModel):
    name: str = Field(max_length=200)
    min_price: int | None = None
    max_price: int | None = None
    bedrooms: int | None = None
    borough: str | None = None
    center_lat: float | None = None
    center_lng: float | None = None
    radius_miles: float | None = None
    amenities: list[str] = Field(default_factory=list)
    min_undervalue_score: float | None = None
    min_rs_probability: float | None = None
    notify_new: bool = True
    notify_price_drop: bool = True
    notify_removed: bool = False
    channels: list[str] = Field(default_factory=lambda: ["push", "email"])


class SavedSearchResponse(SavedSearchCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    is_active: bool
    created_at: datetime


# ── Notifications ─────────────────────────────────────────────────────


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int | None = None
    channel: str
    event_type: str
    message: str
    sent_at: datetime
    read_at: datetime | None = None


# ── Pagination ────────────────────────────────────────────────────────


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int
