"""Notification Celery tasks."""

from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rentradar_workers.celery_app import app
from rentradar_workers.notifications.engine import process_listing_event

logger = logging.getLogger(__name__)


def _get_sync_db() -> Session:
    """Create a sync SQLAlchemy session for Celery tasks."""
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://rentradar:rentradar@localhost:5433/rentradar",
    )
    engine = create_engine(url)
    return Session(engine)


@app.task(name="notifications.ping")
def ping() -> str:
    return "pong"


@app.task(name="notifications.process_event", bind=True, max_retries=3)
def process_event(
    self,
    event_type: str,
    listing: dict[str, Any],
) -> dict[str, Any]:
    """Process a listing event and dispatch notifications.

    Called by dedup/price-change detection when a listing event occurs.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    sendgrid_api_key = os.getenv("SENDGRID_API_KEY", "")
    sendgrid_from_email = os.getenv("SENDGRID_FROM_EMAIL", "alerts@rentradar.app")
    firebase_creds = os.getenv("FIREBASE_CREDENTIALS_PATH", "./firebase-credentials.json")

    db = _get_sync_db()
    try:
        count = process_listing_event(
            db,
            redis_url,
            event_type,
            listing,
            sendgrid_api_key=sendgrid_api_key,
            sendgrid_from_email=sendgrid_from_email,
            firebase_credentials_path=firebase_creds,
        )
        return {"dispatched": count, "event_type": event_type, "listing_id": listing.get("id")}
    except Exception as exc:
        logger.exception("Notification processing failed for listing %s", listing.get("id"))
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        db.close()
