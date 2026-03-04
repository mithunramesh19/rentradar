"""Tests for shared Pydantic schemas."""

import pytest
from pydantic import ValidationError

from rentradar_common.schemas import (
    ListingCreate,
    ListingDetailResponse,
    ListingFilters,
    ListingResponse,
    NotificationResponse,
    PaginatedResponse,
    SavedSearchCreate,
    SavedSearchResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
)


class TestListingCreate:
    def test_valid(self):
        data = ListingCreate(
            address="123 Main St",
            borough="Manhattan",
            price=2500,
            bedrooms=2,
            bathrooms=1.0,
            source="streeteasy",
            source_url="https://streeteasy.com/listing/123",
        )
        assert data.price == 2500

    def test_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            ListingCreate(
                address="x", borough="Manhattan", price=0,
                bedrooms=1, bathrooms=1, source="streeteasy",
                source_url="https://example.com",
            )


class TestListingFilters:
    def test_defaults(self):
        f = ListingFilters()
        assert f.page == 1
        assert f.per_page == 20
        assert f.sort_order == "desc"

    def test_invalid_sort_order(self):
        with pytest.raises(ValidationError):
            ListingFilters(sort_order="random")

    def test_per_page_max(self):
        with pytest.raises(ValidationError):
            ListingFilters(per_page=200)


class TestUserCreate:
    def test_valid(self):
        u = UserCreate(email="test@example.com", password="securepass")
        assert u.email == "test@example.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserCreate(email="not-an-email", password="securepass")

    def test_short_password(self):
        with pytest.raises(ValidationError):
            UserCreate(email="test@example.com", password="short")


class TestSavedSearchCreate:
    def test_defaults(self):
        s = SavedSearchCreate(name="Test Search")
        assert s.notify_new is True
        assert s.channels == ["push", "email"]


class TestPaginatedResponse:
    def test_generic(self):
        resp = PaginatedResponse[int](items=[1, 2, 3], total=10, page=1, per_page=3, pages=4)
        assert len(resp.items) == 3
        assert resp.pages == 4


class TestTokenResponse:
    def test_default_type(self):
        t = TokenResponse(access_token="abc", refresh_token="def")
        assert t.token_type == "bearer"
