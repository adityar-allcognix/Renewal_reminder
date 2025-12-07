"""
Celery Application Configuration
Background task processing for renewal reminders system
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

# Create Celery app
celery_app = Celery(
    "renewal_reminders",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.reminder_tasks",
        "app.tasks.communication_tasks",
        "app.tasks.rag_tasks"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task settings
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    
    # Result backend settings
    result_expires=86400,  # 24 hours
    
    # Concurrency
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
)

# Celery Beat schedule
celery_app.conf.beat_schedule = {
    # Check for renewals every hour
    "check-renewals-hourly": {
        "task": "app.tasks.reminder_tasks.check_and_create_reminders",
        "schedule": crontab(minute=0),  # Every hour at minute 0
    },
    
    # Send pending reminders every 5 minutes
    "send-reminders": {
        "task": "app.tasks.reminder_tasks.send_pending_reminders",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    
    # Update policy statuses daily at midnight
    "update-policy-statuses": {
        "task": "app.tasks.reminder_tasks.update_policy_statuses",
        "schedule": crontab(hour=0, minute=0),
    },
    
    # Calculate engagement scores daily at 2 AM
    "calculate-engagement": {
        "task": "app.tasks.reminder_tasks.calculate_engagement_scores",
        "schedule": crontab(hour=2, minute=0),
    },
    
    # Process retention outreach daily at 9 AM
    "retention-outreach": {
        "task": "app.tasks.communication_tasks.process_retention_outreach",
        "schedule": crontab(hour=9, minute=0),
    },
}


# Task routing
celery_app.conf.task_routes = {
    "app.tasks.reminder_tasks.*": {"queue": "reminders"},
    "app.tasks.communication_tasks.*": {"queue": "communications"},
    "app.tasks.rag_tasks.*": {"queue": "rag"},
}
