"""Nối định danh Drive với database tài khoản/tương tác, không nhập nội dung."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content
from app.models.enums import ContentStatus, ContentType
from app.models.interaction_target import InteractionTarget
from app.schemas.public import ContentOut
from app.services.drive_catalog import catalog


async def published_cms_target(
    session: AsyncSession, public_id: int, type_: ContentType
) -> Content | None:
    if public_id == 0 or abs(public_id) > 2**53 - 1:
        return None
    return await session.scalar(
        select(Content)
        .join(InteractionTarget, InteractionTarget.content_id == Content.id)
        .where(
            InteractionTarget.id == public_id,
            Content.type == type_,
            Content.status == ContentStatus.published,
        )
    )


async def drive_content(content_id: int, type_: ContentType) -> ContentOut | None:
    content = await catalog.get(content_id)
    return content if content is not None and content.type == type_ else None


async def ensure_drive_target(session: AsyncSession, content: ContentOut) -> None:
    file_id = content._drive["id"]
    existing = await session.get(InteractionTarget, content.id)
    if existing is not None:
        if existing.drive_file_id != file_id:
            raise HTTPException(409, "Định danh file Drive bị trùng")
        return
    await session.execute(
        insert(InteractionTarget)
        .values(id=content.id, drive_file_id=file_id)
        .on_conflict_do_nothing(index_elements=[InteractionTarget.id])
    )
    await session.commit()
    # Cũng kiểm tra trường hợp hai file được thêm đồng thời có cùng hash.
    existing = await session.get(InteractionTarget, content.id)
    if existing is None or existing.drive_file_id != file_id:
        raise HTTPException(409, "Định danh file Drive bị trùng")
