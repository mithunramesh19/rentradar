"""Scraper Celery tasks — run_scraper and scrape_all."""

from __future__ import annotations

import logging
import os
from typing import Any

from celery import group

from rentradar_common.constants import DEFAULT_SCRAPE_INTERVALS, ListingSource
from rentradar_workers.celery_app import app
from rentradar_workers.scrapers.base import BaseScraper, SourceConfig

logger = logging.getLogger(__name__)

# Registry of scraper classes keyed by source name.
# Each scraper module registers itself on import via register_scraper().
_SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {}


def register_scraper(source: ListingSource, cls: type[BaseScraper]) -> None:
    """Register a scraper class for a source."""
    _SCRAPER_REGISTRY[source.value] = cls
    logger.debug("Registered scraper for %s: %s", source, cls.__name__)


def get_scraper(source: str) -> BaseScraper:
    """Instantiate the scraper for the given source name."""
    cls = _SCRAPER_REGISTRY.get(source)
    if cls is None:
        raise ValueError(f"No scraper registered for source: {source}")
    config = SourceConfig(source=ListingSource(source), base_url="")
    return cls(config)


@app.task(name="scrapers.ping")
def ping() -> str:
    """Health check task."""
    return "pong"


@app.task(
    name="scrapers.run_scraper",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def run_scraper(self: Any, source: str) -> dict[str, Any]:
    """Run a single scraper by source name.

    Returns summary dict with count and source.
    """
    logger.info("Starting scraper task for %s", source)
    try:
        scraper = get_scraper(source)
        listings = scraper.scrape_with_metrics()
        return {
            "source": source,
            "count": len(listings),
            "status": "ok",
        }
    except ValueError:
        logger.exception("Unknown source: %s", source)
        return {"source": source, "count": 0, "status": "error", "error": f"unknown source: {source}"}
    except Exception as exc:
        logger.exception("Scraper failed for %s", source)
        raise self.retry(exc=exc)


@app.task(name="scrapers.scrape_all")
def scrape_all() -> dict[str, Any]:
    """Fan out scraper tasks for all enabled sources.

    Uses Celery group for parallel execution.
    """
    sources = [s.value for s in ListingSource if s.value in _SCRAPER_REGISTRY]
    if not sources:
        logger.warning("No scrapers registered")
        return {"dispatched": 0, "sources": []}

    logger.info("Dispatching scrapers for %d sources: %s", len(sources), sources)
    job = group(run_scraper.s(source) for source in sources)
    job.apply_async()
    return {"dispatched": len(sources), "sources": sources}


# ── Listing removal detection ────────────────────────────────────────

STALE_THRESHOLD_HOURS = int(os.getenv("STALE_THRESHOLD_HOURS", "48"))


@app.task(name="scrapers.detect_removed")
def detect_removed() -> dict[str, Any]:
    """Mark listings as removed if not seen for STALE_THRESHOLD_HOURS.

    Flow: 48h stale → status=removed → emit REMOVED event for notifications.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import create_engine, text

    db_url = os.getenv("DATABASE_URL", "postgresql://localhost/rentradar")
    engine = create_engine(db_url)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_THRESHOLD_HOURS)

    with engine.begin() as conn:
        # Find stale active listings
        result = conn.execute(
            text("""
                UPDATE listings
                SET status = 'removed', updated_at = NOW()
                WHERE status = 'active'
                  AND last_seen_at < :cutoff
                RETURNING id, canonical_hash, address
            """),
            {"cutoff": cutoff},
        )
        removed = result.fetchall()

        # Emit REMOVED events for notification engine
        for row in removed:
            conn.execute(
                text("""
                    INSERT INTO listing_events (listing_id, event_type, created_at)
                    VALUES (:listing_id, 'removed', NOW())
                """),
                {"listing_id": row[0]},
            )

    count = len(removed)
    if count:
        logger.info("Marked %d listings as removed (stale > %dh)", count, STALE_THRESHOLD_HOURS)
    else:
        logger.debug("No stale listings found")

    return {"removed_count": count, "threshold_hours": STALE_THRESHOLD_HOURS}
