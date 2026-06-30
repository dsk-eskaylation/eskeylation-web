"""Sinh slug duy nhất từ title (bỏ dấu tiếng Việt)."""

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content


async def unique_slug(
    session: AsyncSession, title: str, *, exclude_id: int | None = None
) -> str:
    base = slugify(title) or "noi-dung"
    candidate = base
    i = 2
    while await _exists(session, candidate, exclude_id):
        candidate = f"{base}-{i}"
        i += 1
    return candidate


async def _exists(
    session: AsyncSession, slug: str, exclude_id: int | None
) -> bool:
    stmt = select(Content.id).where(Content.slug == slug)
    if exclude_id is not None:
        stmt = stmt.where(Content.id != exclude_id)
    return (await session.scalar(stmt)) is not None
