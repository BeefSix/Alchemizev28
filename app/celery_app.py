# app/celery_app.py
from celery import Celery
from app.core.config import settings # Assuming you have app.core.config

# Initialize Celery app
# Use environment variables for broker URL in production
celery_app = Celery(
    "alchemize_worker", # Name of your Celery app
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.workers.tasks'] # Tell Celery where to find your tasks
)

# Optional: Celery configuration for timezone, etc.
celery_app.conf.update(
    task_track_started=True,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True, # Important for Docker/startup
    result_expires=3600, # Results expire after 1 hour
)

# Autodiscover tasks if you have multiple task modules
# celery_app.autodiscover_tasks(['app.workers'])