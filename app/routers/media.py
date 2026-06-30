"""Quản trị media — upload/list/get/delete. Yêu cầu đăng nhập (RBAC)."""

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import PaginationParams, require_role
from app.models.enums import UserRole
from app.models.media import Media
from app.schemas.media import MediaRead
from app.schemas.pagination import Page
from app.services import media as media_service

router = APIRouter(prefix="/admin/media", tags=["media"])

# Ai cũng trong nhóm biên tập đều được quản lý media.
_editor = require_role(UserRole.admin, UserRole.editor, UserRole.author)


@router.post("", response_model=MediaRead, status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile,
    alt_text: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    _: object = Depends(_editor),
) -> MediaRead:
    media = await media_service.create_media(session, file, alt_text)
    return MediaRead.from_model(media)


@router.get("", response_model=Page[MediaRead])
async def list_media(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    _: object = Depends(_editor),
) -> Page[MediaRead]:
    total = await session.scalar(select(func.count()).select_from(Media))
    rows = await session.scalars(
        select(Media)
        .order_by(Media.created_at.desc(), Media.id.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    return Page.create(
        items=[MediaRead.from_model(m) for m in rows],
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{media_id}", response_model=MediaRead)
async def get_media(
    media_id: int,
    session: AsyncSession = Depends(get_session),
    _: object = Depends(_editor),
) -> MediaRead:
    media = await session.get(Media, media_id)
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy media"
        )
    return MediaRead.from_model(media)


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    media_id: int,
    session: AsyncSession = Depends(get_session),
    _: object = Depends(_editor),
) -> None:
    media = await session.get(Media, media_id)
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy media"
        )
    await media_service.delete_media(session, media)
