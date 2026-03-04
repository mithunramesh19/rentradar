"""Initial schema — all core tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable PostGIS
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # --- listings ---
    op.create_table(
        "listings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("borough", sa.String(20), nullable=False),
        sa.Column("neighborhood", sa.String(100), nullable=True),
        sa.Column("location", Geometry("POINT", srid=4326), nullable=True),
        sa.Column("price", sa.Integer, nullable=False),
        sa.Column("bedrooms", sa.SmallInteger, nullable=False),
        sa.Column("bathrooms", sa.Float, nullable=False),
        sa.Column("sqft", sa.Integer, nullable=True),
        sa.Column("amenities", JSONB, server_default="[]", nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("undervalue_score", sa.Float, nullable=True),
        sa.Column("rs_probability", sa.Float, nullable=True),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("canonical_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("source_count", sa.SmallInteger, server_default="1", nullable=False),
        sa.Column("days_on_market", sa.Integer, nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_listings_canonical_hash", "listings", ["canonical_hash"], unique=True)
    op.create_index("ix_listings_location", "listings", ["location"], postgresql_using="gist")
    op.create_index("ix_listings_status", "listings", ["status"])
    op.create_index("ix_listings_borough", "listings", ["borough"])
    op.create_index("ix_listings_price", "listings", ["price"])
    op.create_index("ix_listings_bedrooms", "listings", ["bedrooms"])

    # --- listing_sources ---
    op.create_table(
        "listing_sources",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "listing_id",
            sa.BigInteger,
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False, unique=True),
        sa.Column("source_listing_id", sa.String(100), nullable=True),
        sa.Column("raw_data", JSONB, server_default="{}", nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("listing_id", "source", name="uq_listing_source"),
    )
    op.create_index("ix_listing_sources_listing_id", "listing_sources", ["listing_id"])
    op.create_index("ix_listing_sources_source_url", "listing_sources", ["source_url"], unique=True)

    # --- price_history ---
    op.create_table(
        "price_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "listing_id",
            sa.BigInteger,
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Integer, nullable=False),
        sa.Column("previous_price", sa.Integer, nullable=True),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_price_history_listing_id", "price_history", ["listing_id"])
    op.create_index("ix_price_history_recorded_at", "price_history", ["recorded_at"])

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("fcm_token", sa.String(500), nullable=True),
        sa.Column("notification_preferences", JSONB, server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- saved_searches ---
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("min_price", sa.Integer, nullable=True),
        sa.Column("max_price", sa.Integer, nullable=True),
        sa.Column("bedrooms", sa.Integer, nullable=True),
        sa.Column("borough", sa.String(20), nullable=True),
        sa.Column("center_lat", sa.Float, nullable=True),
        sa.Column("center_lng", sa.Float, nullable=True),
        sa.Column("radius_miles", sa.Float, nullable=True),
        sa.Column("amenities", JSONB, server_default="[]", nullable=False),
        sa.Column("min_undervalue_score", sa.Float, nullable=True),
        sa.Column("min_rs_probability", sa.Float, nullable=True),
        sa.Column("notify_new", sa.Boolean, server_default="true", nullable=False),
        sa.Column("notify_price_drop", sa.Boolean, server_default="true", nullable=False),
        sa.Column("notify_removed", sa.Boolean, server_default="false", nullable=False),
        sa.Column("channels", JSONB, server_default='["push","email"]', nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_saved_searches_user_id", "saved_searches", ["user_id"])
    op.create_index("ix_saved_searches_is_active", "saved_searches", ["is_active"])

    # --- notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "listing_id",
            sa.BigInteger,
            sa.ForeignKey("listings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_sent_at", "notifications", ["sent_at"])

    # --- rent_stabilized_buildings ---
    op.create_table(
        "rent_stabilized_buildings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("zip_code", sa.String(10), nullable=False),
        sa.Column("building_number", sa.String(20), nullable=False),
        sa.Column("street_name", sa.String(100), nullable=False),
        sa.Column("street_suffix", sa.String(20), nullable=True),
        sa.Column("building_number_2", sa.String(20), nullable=True),
        sa.Column("street_name_2", sa.String(100), nullable=True),
        sa.Column("street_suffix_2", sa.String(20), nullable=True),
        sa.Column("city", sa.String(50), nullable=False, server_default="NEW YORK"),
        sa.Column("county_code", sa.Integer, nullable=False, server_default="62"),
        sa.Column("status1", sa.String(50), nullable=False),
        sa.Column("status2", sa.String(50), nullable=True),
        sa.Column("status3", sa.String(50), nullable=True),
        sa.Column("block", sa.Integer, nullable=False),
        sa.Column("lot", sa.Integer, nullable=False),
        sa.Column("bbl", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_rs_zip_street", "rent_stabilized_buildings", ["zip_code", "street_name"])
    op.create_index("ix_rs_block_lot", "rent_stabilized_buildings", ["block", "lot"])
    op.create_index("ix_rs_bbl", "rent_stabilized_buildings", ["bbl"])

    # --- building_permits ---
    op.create_table(
        "building_permits",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("permit_number", sa.String(50), nullable=False, unique=True),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("borough", sa.String(20), nullable=False),
        sa.Column("location", Geometry("POINT", srid=4326), nullable=True),
        sa.Column("permit_type", sa.String(30), nullable=False),
        sa.Column("residential_units", sa.Integer, nullable=True),
        sa.Column("estimated_cost", sa.BigInteger, nullable=True),
        sa.Column("filing_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approval_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("raw_data", JSONB, server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_building_permits_location", "building_permits", ["location"], postgresql_using="gist"
    )


def downgrade() -> None:
    op.drop_table("building_permits")
    op.drop_table("rent_stabilized_buildings")
    op.drop_table("notifications")
    op.drop_table("saved_searches")
    op.drop_table("users")
    op.drop_table("price_history")
    op.drop_table("listing_sources")
    op.drop_table("listings")
