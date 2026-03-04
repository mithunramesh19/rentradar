"""Scraper Celery tasks."""

from rentradar_workers.celery_app import app


@app.task(name="scrapers.ping")
def ping() -> str:
    """Health check task."""
    return "pong"
