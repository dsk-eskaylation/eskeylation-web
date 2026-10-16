"""Nối định danh Drive với database tài khoản/tương tác, không nhập nội dung."""

from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ContentType
from app.models.interaction_target import InteractionTarget
from app.schemas.public import ContentOut
from app.services.drive_catalog import catalog


async def drive_content(content_id: int, type_: ContentType) -> ContentOut | None:
    return next(
        (c for c in await catalog.items() if c.id == content_id and c.type == type_),
        None,
    )


async def ensure_drive_target(session: AsyncSession, content: ContentOut) -> None:
    file_id = content.body["drive_file_id"]
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
