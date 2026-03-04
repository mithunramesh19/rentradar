api: uvicorn rentradar.main:app --host 0.0.0.0 --port ${PORT:-8000}
worker: celery -A rentradar_workers.celery_app worker --loglevel=info --concurrency=4
beat: celery -A rentradar_workers.celery_app beat --loglevel=info
