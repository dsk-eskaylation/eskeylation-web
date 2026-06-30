"""CMS — quản lý nội dung (tạo/sửa/workflow). Yêu cầu đăng nhập (RBAC)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.dependencies import PaginationParams, require_role
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType, UserRole
from app.models.media import ContentMedia
from app.models.user import User
from app.schemas.admin import ContentAdminRead, ContentCreate, ContentUpdate
from app.schemas.pagination import Page
from app.services import content_admin

router = APIRouter(prefix="/admin/content", tags=["cms"])

# Tạo/sửa: cả nhóm biên tập. Publish/xoá: chỉ editor + admin.
_editor = require_role(UserRole.admin, UserRole.editor, UserRole.author)
_publisher = require_role(UserRole.admin, UserRole.editor)


async def _load(content_id: int, session: AsyncSession) -> Content:
    content = await content_admin.get_with_media(session, content_id)
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nội dung"
        )
    return content


@router.post("", response_model=ContentAdminRead, status_code=status.HTTP_201_CREATED)
async def create_content(
    data: ContentCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_editor),
) -> ContentAdminRead:
    content = await content_admin.create_content(session, data, user.id)
    return ContentAdminRead.from_model(content)


@router.get("", response_model=Page[ContentAdminRead])
async def list_content(
    pagination: PaginationParams = Depends(),
    type: ContentType | None = None,
    content_status: ContentStatus | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_editor),
) -> Page[ContentAdminRead]:
    base = select(Content)
    if type is not None:
        base = base.where(Content.type == type)
    if content_status is not None:
        base = base.where(Content.status == content_status)

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = await session.scalars(
        base.options(
            selectinload(Content.media_links).selectinload(ContentMedia.media)
        )
        .order_by(Content.updated_at.desc(), Content.id.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    return Page.create(
        items=[ContentAdminRead.from_model(c) for c in rows],
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{content_id}", response_model=ContentAdminRead)
async def get_content(
    content_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_editor),
) -> ContentAdminRead:
    return ContentAdminRead.from_model(await _load(content_id, session))


@router.patch("/{content_id}", response_model=ContentAdminRead)
async def update_content(
    content_id: int,
    data: ContentUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_editor),
) -> ContentAdminRead:
    content = await _load(content_id, session)
    updated = await content_admin.update_content(session, content, data)
    return ContentAdminRead.from_model(updated)


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(
    content_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_publisher),
) -> None:
    content = await _load(content_id, session)
    await content_admin.delete_content(session, content)


@router.post("/{content_id}/publish", response_model=ContentAdminRead)
async def publish_content(
    content_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_publisher),
) -> ContentAdminRead:
    content = await _load(content_id, session)
    return ContentAdminRead.from_model(await content_admin.publish(session, content))


@router.post("/{content_id}/unpublish", response_model=ContentAdminRead)
async def unpublish_content(
    content_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_publisher),
) -> ContentAdminRead:
    content = await _load(content_id, session)
    updated = await content_admin.set_status(session, content, ContentStatus.draft)
    return ContentAdminRead.from_model(updated)


@router.post("/{content_id}/archive", response_model=ContentAdminRead)
async def archive_content(
    content_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_publisher),
) -> ContentAdminRead:
    content = await _load(content_id, session)
    updated = await content_admin.set_status(
        session, content, ContentStatus.archived
    )
    return ContentAdminRead.from_model(updated)


@router.post(
    "/{content_id}/duplicate",
    response_model=ContentAdminRead,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_content(
    content_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_editor),
) -> ContentAdminRead:
    content = await _load(content_id, session)
    copy = await content_admin.duplicate(session, content, user.id)
    return ContentAdminRead.from_model(copy)
