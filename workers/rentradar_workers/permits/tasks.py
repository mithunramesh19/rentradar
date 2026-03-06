"""Permit tracking Celery tasks."""

from __future__ import annotations

import logging
import os

from rentradar_workers.celery_app import app

log = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://rentradar:rentradar@localhost:5433/rentradar")


@app.task(name="permits.ping")
def ping() -> str:
    return "pong"


@app.task(name="permits.ingest_daily", bind=True, max_retries=2)
def ingest_daily(self, days_back: int = 1) -> dict:
    """Daily permit ingestion from NYC Open Data."""
    from rentradar_workers.permits.tracker import ingest_daily_permits

    try:
        return ingest_daily_permits(DB_URL, days_back=days_back)
    except Exception as exc:
        log.exception("Permit ingestion failed")
        raise self.retry(exc=exc, countdown=300)


@app.task(name="permits.check_proximity_alerts", bind=True)
def check_proximity_alerts(self, radius_miles: float = 0.25, days_back: int = 7) -> dict:
    """Check for new permits near active listings."""
    from rentradar_workers.permits.tracker import check_proximity_alerts as _check

    alerts = _check(DB_URL, radius_miles=radius_miles, days_back=days_back)
    return {"status": "ok", "alerts_count": len(alerts), "alerts": alerts}
