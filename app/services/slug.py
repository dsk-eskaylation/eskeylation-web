"""Sinh slug duy nhất từ title (bỏ dấu tiếng Việt).

Slug unique THEO TYPE (khớp UNIQUE(type, slug) trong DB) — /music/hello và
/photos/hello được phép cùng tồn tại vì route public đã tách theo type.
"""

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content
from app.models.enums import ContentType


async def unique_slug(
    session: AsyncSession,
    title: str,
    content_type: ContentType,
    *,
    exclude_id: int | None = None,
) -> str:
    base = slugify(title) or "noi-dung"
    candidate = base
    i = 2
    while await _exists(session, candidate, content_type, exclude_id):
        candidate = f"{base}-{i}"
        i += 1
    return candidate


async def _exists(
    session: AsyncSession,
    slug: str,
    content_type: ContentType,
    exclude_id: int | None,
) -> bool:
    stmt = select(Content.id).where(
        Content.slug == slug, Content.type == content_type
    )
    if exclude_id is not None:
        stmt = stmt.where(Content.id != exclude_id)
    return (await session.scalar(stmt)) is not None
