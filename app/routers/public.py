"""API công khai: chỉ trả nội dung đã publish, route riêng theo từng loại."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import PaginationParams
from app.models.enums import ContentType
from app.schemas.pagination import Page
from app.schemas.public import ContentOut
from app.services import content_query
from app.services.serialize import content_to_out

router = APIRouter(prefix="/api", tags=["public"])


async def _list_page(
    session: AsyncSession,
    type_: ContentType,
    pagination: PaginationParams,
    q: str | None,
    filters: dict[str, str | None] | None = None,
) -> Page[ContentOut]:
    items, total = await content_query.list_published(
        session,
        type_,
        page=pagination.page,
        page_size=pagination.page_size,
        q=q,
        filters=filters,
    )
    return Page.create(
        items=[content_to_out(c) for c in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def _detail(session: AsyncSession, type_: ContentType, slug: str) -> ContentOut:
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
    session: AsyncSession = Depends(get_session),
) -> Page[ContentOut]:
    return await _list_page(
        session,
        ContentType.music,
        pagination,
        q,
        {"category": category, "artist": artist},
    )


@router.get("/music/{slug}", response_model=ContentOut)
async def get_music(
    slug: str, session: AsyncSession = Depends(get_session)
) -> ContentOut:
    return await _detail(session, ContentType.music, slug)


@router.get("/photos", response_model=Page[ContentOut])
async def list_photos(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(None, description="Tìm theo từ khoá (không dấu)"),
    session: AsyncSession = Depends(get_session),
) -> Page[ContentOut]:
    return await _list_page(session, ContentType.gallery, pagination, q)


@router.get("/photos/{slug}", response_model=ContentOut)
async def get_photo(
    slug: str, session: AsyncSession = Depends(get_session)
) -> ContentOut:
    return await _detail(session, ContentType.gallery, slug)


@router.get("/community", response_model=Page[ContentOut])
async def list_community(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(None, description="Tìm theo từ khoá (không dấu)"),
    session: AsyncSession = Depends(get_session),
) -> Page[ContentOut]:
    return await _list_page(session, ContentType.community, pagination, q)


@router.get("/community/{slug}", response_model=ContentOut)
async def get_community(
    slug: str, session: AsyncSession = Depends(get_session)
) -> ContentOut:
    return await _detail(session, ContentType.community, slug)


@router.get("/homepage", response_model=ContentOut)
async def get_homepage(
    session: AsyncSession = Depends(get_session),
) -> ContentOut:
    items, _ = await content_query.list_published(
        session, ContentType.homepage, page=1, page_size=1
    )
    if not items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chưa có nội dung trang chủ",
        )
    return content_to_out(items[0])
