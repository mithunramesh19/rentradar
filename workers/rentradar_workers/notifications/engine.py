"""Notification engine — SQL pre-filter, Python post-filter, rate limiter, dispatch."""

from __future__ import annotations

import logging
import time
from typing import Any

import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from rentradar_common.constants import NotificationChannel

from .email import render_listing_email, send_email
from .push import format_listing_notification, send_push
from .sse import publish_sse_event

logger = logging.getLogger(__name__)

# Rate limit: max notifications per user per hour
RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW = 3600  # seconds
RATE_LIMIT_PREFIX = "rentradar:ratelimit:notify:"


# ---------------------------------------------------------------------------
# Rate limiter (Redis sliding window)
# ---------------------------------------------------------------------------

def _check_rate_limit(r: redis.Redis, user_id: int) -> bool:
    """Return True if user is within rate limit."""
    key = f"{RATE_LIMIT_PREFIX}{user_id}"
    now = time.time()
    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, now - RATE_LIMIT_WINDOW)
    pipe.zcard(key)
    pipe.zadd(key, {str(now): now})
    pipe.expire(key, RATE_LIMIT_WINDOW)
    results = pipe.execute()
    count = results[1]
    if count >= RATE_LIMIT_MAX:
        logger.warning("Rate limit hit for user %d (%d/%d)", user_id, count, RATE_LIMIT_MAX)
        # Remove the optimistic add
        r.zrem(key, str(now))
        return False
    return True


# ---------------------------------------------------------------------------
# SQL pre-filter: find saved searches matching a listing
# ---------------------------------------------------------------------------

SQL_MATCH_SEARCHES = text("""
    SELECT
        ss.id AS search_id,
        ss.user_id,
        ss.name AS search_name,
        ss.channels,
        ss.min_score,
        ss.amenities,
        u.email,
        u.device_tokens
    FROM saved_searches ss
    JOIN users u ON u.id = ss.user_id
    WHERE ss.is_active = true
      AND (ss.min_price IS NULL OR :price >= ss.min_price)
      AND (ss.max_price IS NULL OR :price <= ss.max_price)
      AND (ss.bedrooms IS NULL OR :bedrooms = ss.bedrooms)
      AND (ss.borough IS NULL OR :borough = ss.borough)
      AND (
          ss.center_lat IS NULL
          OR ss.center_lng IS NULL
          OR ss.radius_km IS NULL
          OR ST_DWithin(
              ST_SetSRID(ST_MakePoint(ss.center_lng, ss.center_lat), 4326)::geography,
              ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
              ss.radius_km * 1000
          )
      )
""")


def find_matching_searches(
    db: Session,
    listing: dict[str, Any],
) -> list[dict[str, Any]]:
    """SQL pre-filter: find saved searches that match a listing."""
    result = db.execute(
        SQL_MATCH_SEARCHES,
        {
            "price": listing.get("price"),
            "bedrooms": listing.get("bedrooms"),
            "borough": listing.get("borough"),
            "lat": listing.get("latitude", 0),
            "lng": listing.get("longitude", 0),
        },
    )
    return [dict(row._mapping) for row in result]


# ---------------------------------------------------------------------------
# Python post-filter (amenities + score threshold)
# ---------------------------------------------------------------------------

def _passes_post_filter(
    search: dict[str, Any],
    listing: dict[str, Any],
) -> bool:
    """Check amenity intersection and score threshold."""
    # Amenity filter: search amenities must be subset of listing amenities
    required_amenities = search.get("amenities") or []
    listing_amenities = listing.get("amenities") or []
    if required_amenities:
        if not set(required_amenities).issubset(set(listing_amenities)):
            return False

    # Score threshold
    min_score = search.get("min_score")
    if min_score is not None:
        listing_score = listing.get("quality_score", 0)
        if listing_score < min_score:
            return False

    return True


# ---------------------------------------------------------------------------
# Dispatch to channels
# ---------------------------------------------------------------------------

def _dispatch(
    channel: str,
    user: dict[str, Any],
    event_type: str,
    listing: dict[str, Any],
    search_name: str,
    *,
    sendgrid_api_key: str,
    sendgrid_from_email: str,
    firebase_credentials_path: str,
    redis_url: str,
) -> None:
    """Dispatch notification to a single channel."""
    if channel == NotificationChannel.PUSH:
        tokens = user.get("device_tokens") or []
        if tokens:
            title, body, data = format_listing_notification(event_type, listing)
            failed = send_push(
                tokens, title, body, data,
                credentials_path=firebase_credentials_path,
            )
            if failed:
                logger.info("Failed FCM tokens for user %s: %s", user["user_id"], failed)

    elif channel == NotificationChannel.EMAIL:
        email_addr = user.get("email")
        if email_addr:
            subject, html = render_listing_email(event_type, [listing], search_name)
            send_email(
                email_addr, subject, html,
                api_key=sendgrid_api_key,
                from_email=sendgrid_from_email,
            )

    elif channel == NotificationChannel.SSE:
        publish_sse_event(
            redis_url,
            user["user_id"],
            event_type,
            {
                "listing_id": listing.get("id"),
                "address": listing.get("address"),
                "price": listing.get("price"),
                "event_type": event_type,
                "search_name": search_name,
            },
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_listing_event(
    db: Session,
    redis_url: str,
    event_type: str,
    listing: dict[str, Any],
    *,
    sendgrid_api_key: str = "",
    sendgrid_from_email: str = "alerts@rentradar.app",
    firebase_credentials_path: str = "./firebase-credentials.json",
) -> int:
    """Process a listing event: match searches, filter, rate-limit, dispatch.

    Returns the number of notifications dispatched.
    """
    # 1. SQL pre-filter
    matches = find_matching_searches(db, listing)
    if not matches:
        return 0

    logger.info(
        "Listing %s matched %d saved searches (event=%s)",
        listing.get("id"),
        len(matches),
        event_type,
    )

    r = redis.from_url(redis_url)
    dispatched = 0

    for search in matches:
        # 2. Python post-filter
        if not _passes_post_filter(search, listing):
            continue

        user_id = search["user_id"]

        # 3. Rate limit check
        if not _check_rate_limit(r, user_id):
            continue

        # 4. Dispatch to each configured channel
        channels = search.get("channels") or [NotificationChannel.SSE]
        for channel in channels:
            try:
                _dispatch(
                    channel,
                    search,
                    event_type,
                    listing,
                    search.get("search_name", "your saved search"),
                    sendgrid_api_key=sendgrid_api_key,
                    sendgrid_from_email=sendgrid_from_email,
                    firebase_credentials_path=firebase_credentials_path,
                    redis_url=redis_url,
                )
                dispatched += 1
            except Exception:
                logger.exception(
                    "Dispatch failed: user=%d channel=%s event=%s",
                    user_id,
                    channel,
                    event_type,
                )

    logger.info("Dispatched %d notifications for listing %s", dispatched, listing.get("id"))
    return dispatched
