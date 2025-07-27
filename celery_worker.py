# celery_worker.py
from app.workers.celery_app import celery_app

# This file is intentionally simple.
# It imports the configured Celery app instance from your `app` package
# and lets Celery's command-line interface handle the rest.

# To run the worker, you use the command:
# celery -A celery_worker.celery_app worker --loglevel=info