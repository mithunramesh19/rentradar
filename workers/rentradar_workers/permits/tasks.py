"""Permit tracking Celery tasks."""

from rentradar_workers.celery_app import app


@app.task(name="permits.ping")
def ping() -> str:
    return "pong"
