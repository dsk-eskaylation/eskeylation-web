"""API công khai: chỉ trả nội dung đã publish, route riêng theo từng loại."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import SessionLocal, get_session
from app.dependencies import PaginationParams
from app.models.enums import ContentType
from app.schemas.album import AlbumDetail, AlbumOut, GenreCount
from app.schemas.pagination import Page
from app.schemas.public import ContentOut
from app.services import albums, content_query
from app.services.catalog_revision import database_revision
from app.services.drive_catalog import catalog
from app.services.serialize import content_to_out

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/catalog")
async def catalog_revision(response: Response) -> dict[str, str | None]:
    """Small shared freshness check; never return Drive IDs or credentials."""
    response.headers["Cache-Control"] = "no-store"
    if get_settings().public_content_source != "drive":
        async with SessionLocal() as session:
            return {"revision": await database_revision(session)}
    await catalog.items()
    return {"revision": catalog.revision}


@router.get("/drive/thumbnails/{file_id}")
async def drive_thumbnail(file_id: str) -> Response:
    if get_settings().public_content_source != "drive":
        raise HTTPException(404, "Không có ảnh thu nhỏ")
    return await catalog.thumbnail(file_id)


async def get_public_session():
    if get_settings().public_content_source == "drive":
        yield None
    else:
        async for session in get_session():
            yield session


async def _list_page(
    session: AsyncSession | None,
    type_: ContentType,
    pagination: PaginationParams,
    q: str | None,
    filters: dict[str, str | None] | None = None,
    album: str | None = None,
) -> Page[ContentOut]:
    if get_settings().public_content_source == "drive":
        # The Drive catalog has no albums.
        if album:
            return Page.create(
                items=[], total=0, page=pagination.page, page_size=pagination.page_size
            )
        return await catalog.page(
            type_, pagination.page, pagination.page_size, q, filters
        )
    items, total = await content_query.list_published(
        session,
        type_,
        page=pagination.page,
        page_size=pagination.page_size,
        q=q,
        filters=filters,
        album=album,
    )
    return Page.create(
        items=[content_to_out(c) for c in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def _detail(
    session: AsyncSession | None, type_: ContentType, slug: str
) -> ContentOut:
    if get_settings().public_content_source == "drive":
        return await catalog.detail(type_, slug)
    content = await content_query.get_published_by_slug(session, type_, slug)
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nội dung"
        )
    return content_to_out(content)


@router.get("/music", response_model=Page[ContentOut])
async def list_music(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(None, description="Tìm theo từ khoá (không dấu)"),
    category: str | None = None,
    artist: str | None = None,
    album: str | None = Query(None, max_length=255),
    session: AsyncSession | None = Depends(get_public_session),
) -> Page[ContentOut]:
    return await _list_page(
        session,
        ContentType.music,
        pagination,
        q,
        {"category": category, "artist": artist},
        album,
    )


@router.get("/music/genres", response_model=list[GenreCount])
async def music_genres(
    session: AsyncSession | None = Depends(get_public_session),
) -> list[GenreCount]:
    if session is None:
        return [GenreCount(name=g, count=0) for g in get_settings().music_genres]
    return await albums.genre_counts(session)


@router.get("/albums", response_model=list[AlbumOut])
async def list_albums(
    session: AsyncSession | None = Depends(get_public_session),
) -> list[AlbumOut]:
    return [] if session is None else await albums.list_public(session)


@router.get("/albums/{slug}", response_model=AlbumDetail)
async def get_album(
    slug: str, session: AsyncSession | None = Depends(get_public_session)
) -> AlbumDetail:
    found = await albums.get_public(session, slug) if session else None
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy album")
    album, count = found
    tracks, _ = await content_query.list_published(
        session, ContentType.music, page=1, page_size=500, album=slug
    )
    return AlbumDetail(
        **albums.to_out(album, count).model_dump(),
        tracks=[content_to_out(c) for c in tracks],
    )


@router.get("/music/{slug}", response_model=ContentOut)
async def get_music(
    slug: str, session: AsyncSession | None = Depends(get_public_session)
) -> ContentOut:
    return await _detail(session, ContentType.music, slug)


@router.get("/photos", response_model=Page[ContentOut])
async def list_photos(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(None, description="Tìm theo từ khoá (không dấu)"),
    session: AsyncSession | None = Depends(get_public_session),
) -> Page[ContentOut]:
    return await _list_page(session, ContentType.gallery, pagination, q)


@router.get("/photos/{slug}", response_model=ContentOut)
async def get_photo(
    slug: str, session: AsyncSession | None = Depends(get_public_session)
) -> ContentOut:
    return await _detail(session, ContentType.gallery, slug)


@router.get("/video", response_model=Page[ContentOut])
async def list_video(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(None, description="Tìm theo từ khoá (không dấu)"),
    category: str | None = None,
    session: AsyncSession | None = Depends(get_public_session),
) -> Page[ContentOut]:
    return await _list_page(
        session, ContentType.video, pagination, q, {"category": category}
    )


@router.get("/video/{slug}", response_model=ContentOut)
async def get_video(
    slug: str, session: AsyncSession | None = Depends(get_public_session)
) -> ContentOut:
    return await _detail(session, ContentType.video, slug)


@router.get("/community", response_model=Page[ContentOut])
async def list_community(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(None, description="Tìm theo từ khoá (không dấu)"),
    session: AsyncSession | None = Depends(get_public_session),
) -> Page[ContentOut]:
    return await _list_page(session, ContentType.community, pagination, q)


@router.get("/community/{slug}", response_model=ContentOut)
async def get_community(
    slug: str, session: AsyncSession | None = Depends(get_public_session)
) -> ContentOut:
    return await _detail(session, ContentType.community, slug)


@router.get("/homepage", response_model=ContentOut)
async def get_homepage(
    session: AsyncSession | None = Depends(get_public_session),
) -> ContentOut:
    if get_settings().public_content_source == "drive":
        return ContentOut(
            id=0,
            type=ContentType.homepage,
            title="Eskaylation",
            slug="homepage",
            body={"source": "google_drive"},
            media=[],
        )
    items, _ = await content_query.list_published(
        session, ContentType.homepage, page=1, page_size=1
    )
    if not items:
        return ContentOut(
            id=0,
            type=ContentType.homepage,
            title="Eskaylation",
            slug="homepage",
            body={
                "source": "s3" if get_settings().storage_backend == "s3" else "database"
            },
            media=[],
        )
    return content_to_out(items[0])
