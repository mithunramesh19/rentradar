"""Celery application configuration."""

import os

from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "rentradar",
    broker=redis_url,
    backend=redis_url,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/New_York",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Auto-discover tasks from worker modules
    include=[
        "rentradar_workers.scrapers.tasks",
        "rentradar_workers.notifications.tasks",
        "rentradar_workers.notifications.price_drop",
        "rentradar_workers.scoring.tasks",
        "rentradar_workers.permits.tasks",
    ],
)

# ── Beat schedule — configurable per source via env vars ──────────────
# Override intervals with env: SCRAPE_INTERVAL_STREETEASY=4 (hours)

from celery.schedules import crontab

from rentradar_common.constants import DEFAULT_SCRAPE_INTERVALS, ListingSource


def _build_beat_schedule() -> dict:
    """Build Celery Beat schedule from defaults + env overrides."""
    schedule = {}
    for source in ListingSource:
        env_key = f"SCRAPE_INTERVAL_{source.value.upper()}"
        default_hours = DEFAULT_SCRAPE_INTERVALS.get(source, 8)
        hours = float(os.getenv(env_key, str(default_hours)))

        # Skip disabled sources (interval <= 0)
        if hours <= 0:
            continue

        schedule[f"scrape-{source.value}"] = {
            "task": "scrapers.run_scraper",
            "schedule": hours * 3600,  # Convert hours to seconds
            "args": [source.value],
        }

    # Listing removal detection — every 12 hours
    schedule["detect-removed-listings"] = {
        "task": "scrapers.detect_removed",
        "schedule": crontab(minute=0, hour="*/12"),
    }

    return schedule


app.conf.beat_schedule = _build_beat_schedule()
