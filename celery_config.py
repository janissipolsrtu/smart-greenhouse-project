#!/usr/bin/env python3
"""
Celery Configuration for Irrigation System
Replaces APScheduler with more robust distributed task queue
"""

from celery import Celery
from datetime import timedelta
import os

# Celery configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://irrigation_user:irrigation_pass@postgres:5432/irrigation_db")

# Create Celery app
celery_app = Celery(
    "irrigation_system",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "celery_tasks",  # Tasks module
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task routing and execution
    task_routes={
        "celery_tasks.check_due_irrigations": {"queue": "irrigation_checks"},
        "celery_tasks.execute_irrigation": {"queue": "irrigation_execution"},
        "celery_tasks.schedule_irrigation_plan": {"queue": "irrigation_scheduling"},
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Disable prefetching for better distribution
    task_acks_late=True,  # Acknowledge tasks only after completion
    worker_disable_rate_limits=False,
    
    # Task retry settings
    task_default_retry_delay=60,  # 1 minute default retry delay
    task_max_retries=3,
    
    # Periodic tasks (replaces APScheduler periodic checking)
    beat_schedule={
        "check-due-irrigations": {
            "task": "celery_tasks.check_due_irrigations",
            "schedule": timedelta(seconds=30),  # Every 30 seconds like APScheduler
            "options": {"queue": "irrigation_checks"},
        },
    },
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

if __name__ == "__main__":
    celery_app.start()