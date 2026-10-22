from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "eskaylation",
    broker=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_default_queue="media",
    worker_prefetch_multiplier=1,
    worker_enable_remote_control=False,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 300},
    beat_schedule={"dispatch-media": {"task": "media.dispatch", "schedule": 15.0}},
    timezone="UTC",
)
