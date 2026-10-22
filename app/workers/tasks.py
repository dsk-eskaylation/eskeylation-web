"""Durable jobs use database leases; broker messages contain IDs only."""

import asyncio
import logging
import time

from redis import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.services import media_jobs
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def heartbeat() -> None:
    with Redis.from_url(
        get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2
    ) as redis:
        redis.set(media_jobs.HEARTBEAT_KEY, str(time.time()), ex=180)


async def _run(operation, *args):
    # No pooled asyncpg connection crosses a fork or asyncio.run boundary.
    engine = create_async_engine(
        get_settings().database_url,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
        hide_parameters=True,
    )
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            return await operation(session, *args)
    finally:
        await engine.dispose()


@celery_app.task(name="media.dispatch", ignore_result=True)
def dispatch() -> None:
    if not get_settings().media_processing_enabled:
        return
    heartbeat()
    jobs = asyncio.run(_run(media_jobs.reserve))
    for media_id, token in jobs:
        try:
            process_media.apply_async(args=[media_id, token], expires=240, retry=False)
        except Exception:
            # Lease expiry recovers a failed publish without losing the DB job.
            logger.warning("media_dispatch_failed media_id=%s", media_id)


@celery_app.task(
    name="media.process",
    ignore_result=True,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=120,
    time_limit=150,
)
def process_media(media_id: int, token: str) -> None:
    if not get_settings().media_processing_enabled:
        return
    heartbeat()
    asyncio.run(_run(media_jobs.process, media_id, token))
    heartbeat()
