"""Postgres outbox and leases: broker failure never loses an upload job."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import Media
from app.services.media_processing import (
    ProcessingError,
    cleanup,
    derived_keys,
    process_file,
)
from app.services.storage import get_storage

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
LEASE_SECONDS = 300
HEARTBEAT_KEY = "eskaylation:media-worker:heartbeat"


def queue(media: Media) -> None:
    media.processing_status = "pending"
    media.processing_attempts = 0
    media.processing_next_at = datetime.now(UTC)
    media.processing_lease_until = None
    media.processing_token = None
    media.processing_error_code = None


async def reserve(session: AsyncSession) -> list[tuple[int, str]]:
    now = datetime.now(UTC)
    active = await session.scalar(
        select(func.count())
        .select_from(Media)
        .where(
            Media.processing_status.in_(["queued", "processing"]),
            Media.processing_lease_until > now,
        )
    )
    capacity = max(0, 2 - (active or 0))
    if not capacity:
        return []
    rows = await session.scalars(
        select(Media)
        .where(
            or_(
                and_(
                    Media.processing_status == "pending",
                    Media.processing_next_at <= now,
                ),
                and_(
                    Media.processing_status.in_(["queued", "processing"]),
                    Media.processing_lease_until <= now,
                ),
            )
        )
        .order_by(Media.processing_next_at, Media.id)
        .limit(capacity)
        .with_for_update(skip_locked=True)
    )
    jobs = []
    for media in rows:
        if media.processing_attempts >= MAX_ATTEMPTS:
            media.processing_status = "failed"
            media.processing_error_code = "worker_interrupted"
            media.processing_token = None
            media.processing_lease_until = None
            continue
        token = str(uuid4())
        media.processing_status = "queued"
        media.processing_token = token
        media.processing_lease_until = now + timedelta(seconds=LEASE_SECONDS)
        jobs.append((media.id, token))
    await session.commit()
    return jobs


async def process(session: AsyncSession, media_id: int, token: str) -> None:
    media = await session.scalar(
        select(Media).where(Media.id == media_id).with_for_update()
    )
    now = datetime.now(UTC)
    if (
        not media
        or media.processing_status != "queued"
        or media.processing_token != token
        or not media.processing_lease_until
        or media.processing_lease_until <= now
    ):
        await session.rollback()
        return
    media.processing_status = "processing"
    media.processing_attempts += 1
    media.processing_lease_until = now + timedelta(seconds=LEASE_SECONDS)
    key, mime = media.storage_key, media.mime_type
    await session.commit()
    storage = get_storage()
    result = None
    error_code = None
    try:
        result = await asyncio.to_thread(
            process_file, storage, media_id, token, key, mime
        )
    except ProcessingError as error:
        error_code = str(error)
    except Exception:
        error_code = "processing_failed"
    # Refresh after external I/O: deletion or lease recovery can happen meanwhile.
    media = await session.scalar(
        select(Media)
        .where(Media.id == media_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if not media or media.processing_token != token:
        await session.rollback()
        if result:
            await asyncio.to_thread(
                cleanup, storage, derived_keys(result["variants"], media_id)
            )
        return
    old_keys: set[str] = set()
    if result is not None:
        old_keys = derived_keys(media.variants, media_id)
        for name, value in result.items():
            setattr(media, name, value)
        media.processing_status = "ready"
        media.processing_error_code = None
    else:
        media.processing_status = (
            "failed" if media.processing_attempts >= MAX_ATTEMPTS else "pending"
        )
        media.processing_next_at = datetime.now(UTC) + timedelta(
            seconds=30 * 2 ** (media.processing_attempts - 1)
        )
        media.processing_error_code = error_code
    media.processing_token = None
    media.processing_lease_until = None
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        # Commit may have succeeded before a connection failed. Retain the
        # unique outputs rather than deleting files the DB might reference.
        raise
    await asyncio.to_thread(cleanup, storage, old_keys)
    logger.info(
        "media_job_finished media_id=%s status=%s attempts=%s error_code=%s",
        media_id,
        media.processing_status,
        media.processing_attempts,
        error_code,
    )
