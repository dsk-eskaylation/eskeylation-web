from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Content
from app.models.enums import ContentStatus, ContentType
from app.models.media import ContentMedia


def _published(type_: ContentType) -> Select:
    return select(Content).where(
        Content.type == type_,
        Content.status == ContentStatus.published,
    )


def _apply_search(stmt: Select, q: str | None) -> Select:
    if not q:
        return stmt
    ts_query = func.plainto_tsquery("simple", func.f_unaccent(q))
    return stmt.where(Content.search_vector.op("@@")(ts_query))


def _apply_filters(stmt: Select, filters: dict[str, str | None] | None) -> Select:
    """Lọc theo trường trong JSONB body, ví dụ category/artist của music."""
    for key, value in (filters or {}).items():
        if value is not None:
            stmt = stmt.where(Content.body[key].astext == value)
    return stmt


async def list_published(
    session: AsyncSession,
    type_: ContentType,
    *,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    filters: dict[str, str | None] | None = None,
) -> tuple[list[Content], int]:
    base = _apply_filters(_apply_search(_published(type_), q), filters)

    total = await session.scalar(select(func.count()).select_from(base.subquery()))

    stmt = base.options(
        selectinload(Content.media_links).selectinload(ContentMedia.media)
    )
    if q:
        rank = func.ts_rank(
            Content.search_vector, func.plainto_tsquery("simple", func.f_unaccent(q))
        )
        stmt = stmt.order_by(rank.desc(), Content.published_at.desc())
    else:
        stmt = stmt.order_by(Content.published_at.desc(), Content.id.desc())

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = list((await session.scalars(stmt)).all())
    return items, total or 0


async def get_published_by_slug(
    session: AsyncSession, type_: ContentType, slug: str
) -> Content | None:
    stmt = (
        _published(type_)
        .where(Content.slug == slug)
        .options(selectinload(Content.media_links).selectinload(ContentMedia.media))
    )
    return await session.scalar(stmt)
