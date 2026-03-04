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

# Beat schedule — configured per source via env vars
app.conf.beat_schedule = {}
