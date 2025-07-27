# app/celery_app.py
from celery import Celery
import os
from app.core.config import settings # Import settings

# The broker URL points to the Redis service in your docker-compose.yml
celery_app = Celery(
    "tasks",
    broker=settings.CELERY_BROKER_URL, # Use settings
    backend=settings.CELERY_RESULT_BACKEND, # Use settings
    include=["app.workers.tasks"]
)

celery_app.conf.update(
    task_track_started=True,
    # Optional: Celery configuration for timezone, etc.
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600, # Results expire after 1 hour
)