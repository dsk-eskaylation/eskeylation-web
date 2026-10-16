from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

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

    if q:
        rank = func.ts_rank(
            Content.search_vector, func.plainto_tsquery("simple", func.f_unaccent(q))
        )
        order = (rank.desc(), Content.published_at.desc())
    else:
        order = (Content.published_at.desc(), Content.id.desc())

    # TỐI ƯU ĐỘ TRỄ (chi phí chính là round-trip mạng tới Supabase, không phải query):
    # 1) Gộp ĐẾM TỔNG vào cùng query lấy dữ liệu bằng window `count(*) OVER()`
    #    -> bớt một round-trip so với việc chạy COUNT riêng.
    # 2) Nạp media trong MỘT round-trip: selectinload(media_links) + joinedload(media)
    #    (media là quan hệ many-to-one nên JOIN không nhân dòng) thay vì hai
    #    selectinload lồng nhau (hai round-trip).
    stmt = (
        base.add_columns(func.count().over().label("total"))
        .options(selectinload(Content.media_links).joinedload(ContentMedia.media))
        .order_by(*order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).all()
    items = [row[0] for row in rows]

    if rows:
        total = rows[0].total
    elif page > 1:
        # Trang vượt phạm vi (hiếm) -> window count không có dòng nào để lấy tổng,
        # đếm lại để total vẫn đúng cho phân trang.
        total = (
            await session.scalar(select(func.count()).select_from(base.subquery()))
        ) or 0
    else:
        total = 0
    return items, total


async def get_published_by_slug(
    session: AsyncSession, type_: ContentType, slug: str
) -> Content | None:
    # Detail: nạp cả media trong MỘT round-trip bằng joinedload (một Content nên
    # JOIN collection chỉ nhân theo số media của đúng bài đó -> .unique() gộp lại).
    stmt = (
        _published(type_)
        .where(Content.slug == slug)
        .options(joinedload(Content.media_links).joinedload(ContentMedia.media))
    )
    return (await session.scalars(stmt)).unique().one_or_none()
