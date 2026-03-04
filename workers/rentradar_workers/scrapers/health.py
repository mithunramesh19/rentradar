"""Scraper health monitoring — Redis metrics + alerting."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from redis import Redis

from rentradar_common.constants import ListingSource

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
METRIC_KEY_PREFIX = "scraper:metrics"
ALERT_KEY = "scraper:alerts"

# Thresholds
MIN_LISTINGS_PER_RUN = int(os.getenv("SCRAPER_MIN_LISTINGS", "5"))
MAX_DURATION_SECONDS = int(os.getenv("SCRAPER_MAX_DURATION", "600"))
MAX_CONSECUTIVE_FAILURES = int(os.getenv("SCRAPER_MAX_FAILURES", "3"))


def _redis() -> Redis:
    return Redis.from_url(REDIS_URL, decode_responses=True)


def record_scrape_result(
    source: str,
    *,
    count: int,
    duration_seconds: float,
    success: bool,
    error: str = "",
) -> None:
    """Record scrape metrics to Redis."""
    r = _redis()
    now = datetime.now(timezone.utc).isoformat()
    key = f"{METRIC_KEY_PREFIX}:{source}"

    metric = {
        "timestamp": now,
        "count": count,
        "duration_seconds": round(duration_seconds, 2),
        "success": success,
        "error": error,
    }

    # Store latest run
    r.hset(f"{key}:latest", mapping={k: json.dumps(v) for k, v in metric.items()})

    # Append to history (keep last 100 runs)
    r.lpush(f"{key}:history", json.dumps(metric))
    r.ltrim(f"{key}:history", 0, 99)

    # Update counters
    if success:
        r.hincrby(f"{key}:counters", "total_success", 1)
        r.hset(f"{key}:counters", "consecutive_failures", 0)
        r.hincrby(f"{key}:counters", "total_listings", count)
    else:
        r.hincrby(f"{key}:counters", "total_failures", 1)
        r.hincrby(f"{key}:counters", "consecutive_failures", 1)

    # Check for alerts
    _check_alerts(r, source, metric)


def _check_alerts(r: Redis, source: str, metric: dict[str, Any]) -> None:
    """Check metric thresholds and emit alerts."""
    key = f"{METRIC_KEY_PREFIX}:{source}"
    counters = r.hgetall(f"{key}:counters")
    consecutive_failures = int(counters.get("consecutive_failures", 0))

    alerts: list[dict[str, Any]] = []

    # Alert: consecutive failures
    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        alerts.append({
            "level": "critical",
            "source": source,
            "message": f"{source} has {consecutive_failures} consecutive failures",
            "timestamp": metric["timestamp"],
        })

    # Alert: low yield
    if metric["success"] and metric["count"] < MIN_LISTINGS_PER_RUN:
        alerts.append({
            "level": "warning",
            "source": source,
            "message": f"{source} yielded only {metric['count']} listings (min: {MIN_LISTINGS_PER_RUN})",
            "timestamp": metric["timestamp"],
        })

    # Alert: slow scrape
    if metric["duration_seconds"] > MAX_DURATION_SECONDS:
        alerts.append({
            "level": "warning",
            "source": source,
            "message": f"{source} took {metric['duration_seconds']}s (max: {MAX_DURATION_SECONDS}s)",
            "timestamp": metric["timestamp"],
        })

    for alert in alerts:
        r.lpush(ALERT_KEY, json.dumps(alert))
        r.ltrim(ALERT_KEY, 0, 199)  # Keep last 200 alerts
        logger.warning("Scraper alert: %s", alert["message"])


def get_health_summary() -> dict[str, Any]:
    """Get health summary for all scrapers."""
    r = _redis()
    summary: dict[str, Any] = {}

    for source in ListingSource:
        key = f"{METRIC_KEY_PREFIX}:{source.value}"
        latest_raw = r.hgetall(f"{key}:latest")
        counters = r.hgetall(f"{key}:counters")

        if not latest_raw:
            summary[source.value] = {"status": "no_data"}
            continue

        latest = {k: json.loads(v) for k, v in latest_raw.items()}
        consecutive_failures = int(counters.get("consecutive_failures", 0))

        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            status = "critical"
        elif not latest.get("success"):
            status = "degraded"
        else:
            status = "healthy"

        summary[source.value] = {
            "status": status,
            "last_run": latest.get("timestamp"),
            "last_count": latest.get("count", 0),
            "last_duration": latest.get("duration_seconds", 0),
            "total_success": int(counters.get("total_success", 0)),
            "total_failures": int(counters.get("total_failures", 0)),
            "total_listings": int(counters.get("total_listings", 0)),
            "consecutive_failures": consecutive_failures,
        }

    # Recent alerts
    recent_alerts_raw = r.lrange(ALERT_KEY, 0, 9)
    summary["recent_alerts"] = [json.loads(a) for a in recent_alerts_raw]

    return summary
