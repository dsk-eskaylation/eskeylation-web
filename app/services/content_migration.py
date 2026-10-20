"""Idempotent migration of verified Drive metadata into editable CMS content."""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content
from app.models.enums import ContentStatus, ContentType
from app.models.interaction_target import InteractionTarget
from app.models.media import ContentMedia, Media


async def import_drive_content(
    session: AsyncSession, item: dict, author_id: int
) -> tuple[int, bool]:
    """Caller owns the transaction; retries never overwrite later CMS edits."""
    public_id = item["public_id"]
    if not -(2**48) <= public_id <= -1:
        raise ValueError("Invalid legacy public ID")
    target = await session.get(InteractionTarget, public_id)
    if target is not None:
        if target.drive_file_id != item["drive_file_id"]:
            raise ValueError("Legacy identity collision")
        if target.content_id is not None:
            return target.content_id, False
    content = Content(
        type=ContentType(item["type"]),
        title=item["title"],
        slug=item["slug"],
        summary=item.get("summary"),
        body=item["body"],
        author_id=author_id,
        status=ContentStatus.published,
        published_at=datetime.now(UTC),
    )
    session.add(content)
    await session.flush()
    # The insert trigger creates a positive target; it has no interactions yet.
    await session.execute(
        delete(InteractionTarget).where(InteractionTarget.id == content.id)
    )
    if target is None:
        session.add(
            InteractionTarget(
                id=public_id,
                content_id=content.id,
                drive_file_id=item["drive_file_id"],
            )
        )
    else:
        target.content_id = content.id
    for position, metadata in enumerate(item["media"]):
        key = metadata["storage_key"]
        if not key.startswith("drive/" + item["drive_file_id"] + "/"):
            raise ValueError("Imported media outside its source namespace")
        media = await session.scalar(select(Media).where(Media.storage_key == key))
        if media is None:
            media = Media(
                **{
                    k: metadata[k]
                    for k in (
                        "storage_key",
                        "mime_type",
                        "size",
                        "width",
                        "height",
                        "duration",
                        "alt_text",
                    )
                }
            )
            session.add(media)
            await session.flush()
        session.add(
            ContentMedia(
                content_id=content.id,
                media_id=media.id,
                position=position,
                is_primary=metadata["is_primary"],
            )
        )
    await session.flush()
    return content.id, True
