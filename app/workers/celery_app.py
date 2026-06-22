from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "eskaylation",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
