"""Two-phase, retryable disposal of expired uploads; never sweep old S3 prefixes."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import ContentMedia, Media
from app.services.media_processing import derived_keys
from app.services.storage import get_storage

logger = logging.getLogger(__name__)


def _candidates(now: datetime):
    return (
        select(Media)
        .where(
            Media.upload_expires_at.is_not(None),
            Media.upload_expires_at <= now,
            ~select(ContentMedia.id).where(ContentMedia.media_id == Media.id).exists(),
            or_(
                Media.processing_lease_until.is_(None),
                Media.processing_lease_until <= now,
            ),
        )
        .order_by(Media.upload_expires_at, Media.id)
        .limit(25)
    )


async def cleanup_expired(
    session: AsyncSession, *, apply: bool = False
) -> dict[str, int]:
    """Preview by default; dispose only explicitly expiring, never-attached uploads."""
    statement = _candidates(datetime.now(UTC))
    if apply:
        statement = statement.with_for_update(skip_locked=True)
    rows = (await session.scalars(statement)).all()
    result = {"candidates": len(rows), "deleted": 0, "failed": 0}
    if not apply or not rows:
        return result
    for media in rows:
        # Persist a tombstone before storage I/O: attachments and new jobs reject it.
        media.cleanup_pending = True
        media.processing_status = "failed"
        media.processing_error_code = "upload_expired"
        media.processing_token = None
        # Reuse the existing lease column to keep concurrent janitors apart.
        media.processing_lease_until = datetime.now(UTC) + timedelta(minutes=5)
    await session.commit()
    storage = get_storage()
    for media in rows:
        keys = derived_keys(media.variants or {}, media.id) | {media.storage_key}
        try:
            for key in sorted(keys):
                await asyncio.to_thread(storage.delete, key)
        except Exception:
            # Keep the DB row/tombstone so a later pass can retry storage deletion.
            media.processing_lease_until = None
            await session.commit()
            result["failed"] += 1
            logger.warning("member_upload_cleanup_storage_failed media_id=%s", media.id)
            continue
        current = await session.scalar(
            select(Media).where(Media.id == media.id).with_for_update()
        )
        if current is not None and current.cleanup_pending:
            await session.delete(current)
            await session.commit()
            result["deleted"] += 1
        else:
            await session.rollback()
    logger.info(
        "member_upload_cleanup candidates=%s deleted=%s failed=%s", *result.values()
    )
    return result
