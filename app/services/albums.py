from fastapi import HTTPException, status
from slugify import slugify
from sqlalchemy import func, select
from sqlalchemy import update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.album import Album
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType
from app.schemas.album import (
    AlbumAdminRead,
    AlbumIn,
    AlbumOut,
    AlbumUpdate,
    GenreCount,
)

_ORDER = (Album.position, Album.year.desc().nulls_last(), Album.title)


def to_out(album: Album, track_count: int) -> AlbumOut:
    return AlbumOut(
        slug=album.slug,
        title=album.title,
        kind=album.kind,
        year=album.year,
        cover_url=album.cover_url,
        description=album.description,
        track_count=track_count,
    )


def to_admin(album: Album, track_count: int) -> AlbumAdminRead:
    return AlbumAdminRead(
        **to_out(album, track_count).model_dump(),
        id=album.id,
        position=album.position,
    )


def _published_music():
    return (Content.type == ContentType.music) & (
        Content.status == ContentStatus.published
    )


async def list_public(session: AsyncSession) -> list[AlbumOut]:
    """Albums with at least one published track."""
    count = func.count(Content.id)
    rows = await session.execute(
        select(Album, count)
        .join(Content, Content.album_id == Album.id)
        .where(_published_music())
        .group_by(Album.id)
        .order_by(*_ORDER)
    )
    return [to_out(album, n) for album, n in rows.all()]


async def get_public(session: AsyncSession, slug: str) -> tuple[Album, int] | None:
    count = func.count(Content.id)
    row = (
        await session.execute(
            select(Album, count)
            .join(Content, Content.album_id == Album.id)
            .where(Album.slug == slug, _published_music())
            .group_by(Album.id)
        )
    ).first()
    return (row[0], row[1]) if row else None


async def genre_counts(session: AsyncSession) -> list[GenreCount]:
    category = Content.body["category"].astext
    rows = await session.execute(
        select(category, func.count())
        .where(_published_music(), category.is_not(None))
        .group_by(category)
    )
    counts = dict(rows.all())
    return [
        GenreCount(name=name, count=counts.get(name, 0))
        for name in get_settings().music_genres
    ]


async def list_admin(session: AsyncSession) -> list[AlbumAdminRead]:
    """Every album, counting tracks in any status."""
    count = func.count(Content.id)
    rows = await session.execute(
        select(Album, count)
        .outerjoin(Content, Content.album_id == Album.id)
        .group_by(Album.id)
        .order_by(*_ORDER)
    )
    return [to_admin(album, n) for album, n in rows.all()]


async def _unique_slug(
    session: AsyncSession, title: str, exclude_id: int | None
) -> str:
    base = slugify(title) or "album"
    candidate, i = base, 2
    while True:
        stmt = select(Album.id).where(Album.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(Album.id != exclude_id)
        if await session.scalar(stmt) is None:
            return candidate
        candidate, i = f"{base}-{i}", i + 1


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Album vừa bị thay đổi bởi thao tác khác — thử lại",
        ) from exc


async def create(session: AsyncSession, data: AlbumIn) -> AlbumAdminRead:
    slug = await _unique_slug(session, data.title, None)
    album = Album(**data.model_dump(), slug=slug)
    session.add(album)
    await _commit(session)
    return to_admin(album, 0)


async def get(session: AsyncSession, album_id: int) -> Album:
    album = await session.get(Album, album_id)
    if album is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy album")
    return album


async def update(
    session: AsyncSession, album: Album, data: AlbumUpdate
) -> AlbumAdminRead:
    fields = data.model_dump(exclude_unset=True)
    if "title" in fields and fields["title"] != album.title:
        album.slug = await _unique_slug(session, fields["title"], album.id)
    for key, value in fields.items():
        setattr(album, key, value)
    await _commit(session)
    count = await session.scalar(
        select(func.count(Content.id)).where(Content.album_id == album.id)
    )
    return to_admin(album, count or 0)


async def delete(session: AsyncSession, album: Album) -> None:
    # ON DELETE SET NULL only clears album_id; a stale track_no would leak to singles.
    await session.execute(
        sql_update(Content)
        .where(Content.album_id == album.id)
        .values(track_no=None, updated_at=func.now())
    )
    await session.delete(album)
    await session.commit()
