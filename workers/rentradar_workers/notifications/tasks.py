"""Notification Celery tasks."""

from rentradar_workers.celery_app import app


@app.task(name="notifications.ping")
def ping() -> str:
    return "pong"
