"""Price drop alert system — wires dedup events to notification engine.

Called after dedup/upsert detects a price change or new listing event.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from rentradar_common.constants import EventType
from rentradar_workers.celery_app import app
from rentradar_workers.notifications.engine import process_listing_event

logger = logging.getLogger(__name__)


def _get_sync_session() -> Session:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://rentradar:rentradar@localhost:5432/rentradar",
    )
    engine = create_engine(url)
    return Session(engine)


def _fetch_listing_dict(db: Session, canonical_hash: str) -> dict[str, Any] | None:
    """Fetch full listing details as a dict for notification formatting."""
    row = db.execute(
        text("""
            SELECT
                id, canonical_hash, address, price_cents,
                bedrooms, bathrooms, sqft,
                lat AS latitude, lng AS longitude,
                neighborhood, borough, listing_data, status
            FROM listings
            WHERE canonical_hash = :hash
        """),
        {"hash": canonical_hash},
    ).fetchone()

    if row is None:
        return None

    mapping = dict(row._mapping)
    # Convert price_cents to dollars for notification formatting
    price_cents = mapping.get("price_cents")
    mapping["price"] = price_cents / 100 if price_cents else None
    return mapping


def dispatch_listing_event(
    canonical_hash: str,
    event_type: EventType,
    *,
    old_price_cents: int | None = None,
) -> int:
    """Fetch listing and dispatch notifications for an event.

    Returns number of notifications dispatched.
    """
    db = _get_sync_session()
    try:
        listing = _fetch_listing_dict(db, canonical_hash)
        if listing is None:
            logger.warning("Listing not found for hash %s", canonical_hash[:12])
            return 0

        # Attach old price for price drop formatting
        if old_price_cents is not None:
            listing["old_price"] = old_price_cents / 100

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return process_listing_event(
            db,
            redis_url,
            event_type.value,
            listing,
            sendgrid_api_key=os.getenv("SENDGRID_API_KEY", ""),
            sendgrid_from_email=os.getenv("SENDGRID_FROM_EMAIL", "alerts@rentradar.app"),
            firebase_credentials_path=os.getenv(
                "FIREBASE_CREDENTIALS_PATH", "./firebase-credentials.json"
            ),
        )
    finally:
        db.close()


@app.task(name="notifications.price_drop_alert", bind=True, max_retries=3)
def price_drop_alert_task(
    self,
    canonical_hash: str,
    event_type: str,
    old_price_cents: int | None = None,
) -> dict[str, Any]:
    """Celery task: dispatch price drop (or other listing event) notifications.

    Intended to be called by the dedup service after upsert detects an event:
        from rentradar_workers.notifications.price_drop import price_drop_alert_task
        price_drop_alert_task.delay(canonical_hash, event.value, old_price_cents=old_price)
    """
    try:
        evt = EventType(event_type)
        count = dispatch_listing_event(
            canonical_hash, evt, old_price_cents=old_price_cents
        )
        return {
            "canonical_hash": canonical_hash,
            "event_type": event_type,
            "dispatched": count,
        }
    except Exception as exc:
        logger.exception("Price drop alert failed for %s", canonical_hash[:12])
        raise self.retry(exc=exc, countdown=30) from exc
