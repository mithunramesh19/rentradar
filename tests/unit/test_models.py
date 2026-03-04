"""Tests for SQLAlchemy ORM models — validates schema definitions."""

from datetime import datetime

from rentradar.models import (
    BuildingPermit,
    Listing,
    ListingSource,
    Notification,
    PriceHistory,
    RentStabilizedBuilding,
    SavedSearch,
    User,
)


class TestListingModel:
    def test_tablename(self):
        assert Listing.__tablename__ == "listings"

    def test_columns_exist(self):
        cols = {c.name for c in Listing.__table__.columns}
        expected = {
            "id", "address", "unit", "borough", "neighborhood", "location",
            "price", "bedrooms", "bathrooms", "sqft", "amenities", "description",
            "undervalue_score", "rs_probability", "quality_score",
            "canonical_hash", "status", "source_count", "days_on_market",
            "first_seen_at", "last_seen_at", "created_at", "updated_at",
        }
        assert expected.issubset(cols)

    def test_canonical_hash_unique(self):
        col = Listing.__table__.c.canonical_hash
        assert col.unique is True

    def test_repr(self):
        listing = Listing(id=1, address="123 Main St", price=2500)
        assert "123 Main St" in repr(listing)


class TestListingSourceModel:
    def test_tablename(self):
        assert ListingSource.__tablename__ == "listing_sources"

    def test_columns_exist(self):
        cols = {c.name for c in ListingSource.__table__.columns}
        expected = {
            "id", "listing_id", "source", "source_url",
            "source_listing_id", "raw_data", "scraped_at",
        }
        assert expected.issubset(cols)

    def test_source_url_unique(self):
        col = ListingSource.__table__.c.source_url
        assert col.unique is True


class TestPriceHistoryModel:
    def test_tablename(self):
        assert PriceHistory.__tablename__ == "price_history"

    def test_columns_exist(self):
        cols = {c.name for c in PriceHistory.__table__.columns}
        expected = {"id", "listing_id", "price", "previous_price", "event_type", "recorded_at"}
        assert expected.issubset(cols)


class TestUserModel:
    def test_tablename(self):
        assert User.__tablename__ == "users"

    def test_email_unique(self):
        col = User.__table__.c.email
        assert col.unique is True

    def test_columns_exist(self):
        cols = {c.name for c in User.__table__.columns}
        expected = {
            "id", "email", "password_hash", "fcm_token",
            "notification_preferences", "created_at",
        }
        assert expected.issubset(cols)


class TestSavedSearchModel:
    def test_tablename(self):
        assert SavedSearch.__tablename__ == "saved_searches"

    def test_columns_exist(self):
        cols = {c.name for c in SavedSearch.__table__.columns}
        expected = {
            "id", "user_id", "name", "min_price", "max_price", "bedrooms",
            "borough", "center_lat", "center_lng", "radius_miles", "amenities",
            "min_undervalue_score", "min_rs_probability",
            "notify_new", "notify_price_drop", "notify_removed", "channels",
            "is_active", "created_at",
        }
        assert expected.issubset(cols)


class TestNotificationModel:
    def test_tablename(self):
        assert Notification.__tablename__ == "notifications"

    def test_columns_exist(self):
        cols = {c.name for c in Notification.__table__.columns}
        expected = {
            "id", "user_id", "listing_id", "channel",
            "event_type", "message", "sent_at", "read_at",
        }
        assert expected.issubset(cols)


class TestRentStabilizedBuildingModel:
    def test_tablename(self):
        assert RentStabilizedBuilding.__tablename__ == "rent_stabilized_buildings"


class TestBuildingPermitModel:
    def test_tablename(self):
        assert BuildingPermit.__tablename__ == "building_permits"

    def test_columns_exist(self):
        cols = {c.name for c in BuildingPermit.__table__.columns}
        expected = {
            "id", "permit_number", "address", "borough", "location",
            "permit_type", "residential_units", "estimated_cost",
            "filing_date", "approval_date", "completion_date",
            "status", "raw_data", "created_at",
        }
        assert expected.issubset(cols)

    def test_permit_number_unique(self):
        col = BuildingPermit.__table__.c.permit_number
        assert col.unique is True
