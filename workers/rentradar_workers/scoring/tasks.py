"""Scoring Celery tasks."""

from rentradar_workers.celery_app import app


@app.task(name="scoring.ping")
def ping() -> str:
    return "pong"
