"""Dedup service — upsert listings with price change detection.

Ported upsert pattern from ~/Desktop/ApartmentScraper/database_manager.py
and extended with price change detection + event emission.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from rentradar_common.constants import EventType, ListingStatus

logger = logging.getLogger(__name__)


def upsert_listing(
    conn: Connection,
    *,
    canonical_hash: str,
    source: str,
    source_url: str,
    address: str,
    price_cents: int | None,
    bedrooms: float | None,
    bathrooms: float | None,
    sqft: int | None,
    lat: float | None = None,
    lng: float | None = None,
    neighborhood: str = "",
    borough: str = "",
    listing_data: dict[str, Any] | None = None,
) -> tuple[str, EventType | None]:
    """Upsert a listing and detect price changes.

    Returns (canonical_hash, event_type_or_none).
    event_type is LISTED for new, PRICE_DROP/PRICE_INCREASE for changes, None for no-change.
    """
    now = datetime.now(timezone.utc)
    data_json = listing_data or {}

    # Check if listing exists and get current price
    existing = conn.execute(
        text("""
            SELECT id, price_cents, status
            FROM listings
            WHERE canonical_hash = :canonical_hash
        """),
        {"canonical_hash": canonical_hash},
    ).fetchone()

    if existing is None:
        # New listing — INSERT
        conn.execute(
            text("""
                INSERT INTO listings
                    (canonical_hash, source, source_url, address,
                     price_cents, bedrooms, bathrooms, sqft,
                     lat, lng, neighborhood, borough,
                     listing_data, status, first_seen_at, last_seen_at)
                VALUES
                    (:canonical_hash, :source, :source_url, :address,
                     :price_cents, :bedrooms, :bathrooms, :sqft,
                     :lat, :lng, :neighborhood, :borough,
                     :listing_data, :status, :now, :now)
            """),
            {
                "canonical_hash": canonical_hash,
                "source": source,
                "source_url": source_url,
                "address": address,
                "price_cents": price_cents,
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "sqft": sqft,
                "lat": lat,
                "lng": lng,
                "neighborhood": neighborhood,
                "borough": borough,
                "listing_data": str(data_json),
                "status": ListingStatus.ACTIVE,
                "now": now,
            },
        )
        logger.info("New listing: %s at %s", canonical_hash[:12], address)
        return canonical_hash, EventType.LISTED

    # Existing listing — UPDATE + price change detection
    listing_id = existing[0]
    old_price = existing[1]
    old_status = existing[2]

    event: EventType | None = None

    # Detect price change
    if price_cents is not None and old_price is not None and price_cents != old_price:
        if price_cents < old_price:
            event = EventType.PRICE_DROP
        else:
            event = EventType.PRICE_INCREASE

        # Record price history
        conn.execute(
            text("""
                INSERT INTO price_history (listing_id, price_cents, recorded_at)
                VALUES (:listing_id, :price_cents, :recorded_at)
            """),
            {"listing_id": listing_id, "price_cents": price_cents, "recorded_at": now},
        )
        logger.info(
            "Price change for %s: %s → %s (%s)",
            canonical_hash[:12],
            old_price,
            price_cents,
            event,
        )

    # Detect relisting
    if old_status == ListingStatus.REMOVED:
        event = EventType.RELISTED
        logger.info("Relisted: %s", canonical_hash[:12])

    # Update the listing
    conn.execute(
        text("""
            UPDATE listings
            SET source_url = :source_url,
                address = :address,
                price_cents = :price_cents,
                bedrooms = :bedrooms,
                bathrooms = :bathrooms,
                sqft = :sqft,
                lat = COALESCE(:lat, lat),
                lng = COALESCE(:lng, lng),
                neighborhood = COALESCE(NULLIF(:neighborhood, ''), neighborhood),
                borough = COALESCE(NULLIF(:borough, ''), borough),
                listing_data = :listing_data,
                status = :status,
                last_seen_at = :now
            WHERE canonical_hash = :canonical_hash
        """),
        {
            "source_url": source_url,
            "address": address,
            "price_cents": price_cents,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "sqft": sqft,
            "lat": lat,
            "lng": lng,
            "neighborhood": neighborhood,
            "borough": borough,
            "listing_data": str(data_json),
            "status": ListingStatus.ACTIVE,
            "now": now,
            "canonical_hash": canonical_hash,
        },
    )

    return canonical_hash, event
