# app/celery_app.py
from celery import Celery
from celery.signals import worker_ready, worker_shutdown, task_failure
from app.core.config import settings
from app.core.logger import logger as base_logger

# Initialize Celery app
celery_app = Celery(
    "zuexis_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        'app.workers.tasks',        # All tasks are now in this single module
    ]
)

# Initialize logger
logger = base_logger

# Configure Celery
celery_app.conf.update(
    task_track_started=True,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,

    # Enhanced broker transport options for better connection handling
    broker_transport_options={
        'health_check_interval': 30,  # Check broker health every 30 seconds
        'retry_on_timeout': True,
        'max_retries': 3,
    },
    
    # Enhanced error handling configuration
    task_reject_on_worker_lost=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Connection retry settings
    broker_connection_max_retries=10,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'monitoring-check': {
            'task': 'app.workers.tasks.monitoring_task',
            'schedule': 60.0,  # Run every 60 seconds
        },
    },
)

# Celery signal handlers for enhanced monitoring
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Handle worker ready event."""
    logger.info(f"✅ Celery worker {sender} is ready and connected")

@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Handle worker shutdown event."""
    logger.info(f"🔄 Celery worker {sender} is shutting down")

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwargs):
    """Handle task failure events with enhanced logging."""
    error_msg = str(exception) if exception else "Unknown error"
    
    # Log specific error patterns
    if "not enough values to unpack" in error_msg:
        logger.error(f"🐛 Celery trace unpacking error in task {task_id}: {error_msg}")
        logger.error("This is likely an internal Celery issue - consider restarting workers")
    elif "redis" in error_msg.lower():
        logger.error(f"🔴 Redis connection error in task {task_id}: {error_msg}")
    else:
        logger.error(f"❌ Task {task_id} failed: {error_msg}")
    
    if traceback:
        logger.debug(f"Task {task_id} traceback: {traceback}")
