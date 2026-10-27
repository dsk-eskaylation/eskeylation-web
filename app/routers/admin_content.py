"""CMS — quản lý nội dung (tạo/sửa/workflow). Yêu cầu đăng nhập (RBAC)."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.dependencies import PaginationParams, require_role
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType, MusicProvider, UserRole
from app.models.media import ContentMedia
from app.models.user import User
from app.schemas.admin import ContentAdminRead, ContentCreate, ContentUpdate
from app.schemas.pagination import Page
from app.services import activity, content_admin, drive_http
from app.services.ratelimit import check_rate
from app.services.sanitize import music_source

router = APIRouter(prefix="/admin/content", tags=["cms"])

# Fixed endpoints only; the user's URL is just a query param, never fetched (no SSRF).
_OEMBED_ENDPOINTS = {
    MusicProvider.soundcloud: "https://soundcloud.com/oembed",
    MusicProvider.youtube: "https://www.youtube.com/oembed",
    MusicProvider.vimeo: "https://vimeo.com/api/oembed.json",
}

# Tạo/sửa: cả nhóm biên tập. Publish/xoá: chỉ editor + admin.
_editor = require_role(UserRole.admin, UserRole.editor, UserRole.author)
_publisher = require_role(UserRole.admin, UserRole.editor)


async def _load(
    content_id: int, session: AsyncSession, *, lock: bool = False
) -> Content:
    content = await content_admin.get_with_media(session, content_id, lock=lock)
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nội dung"
        )
    return content


def _ensure_can_edit(content: Content, user: User) -> None:
    """Author chỉ được xem chi tiết/sửa/nhân bản nội dung của CHÍNH MÌNH.
    Editor/admin toàn quyền. Chống IDOR trong nhóm biên tập."""
    if user.role == UserRole.author and content.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ được thao tác trên nội dung của chính mình",
        )


@router.get("/oembed")
async def music_oembed(
    url: str = Query(max_length=500),
    user: User = Depends(_editor),
) -> dict[str, str | None]:
    found = music_source(url)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Chỉ hỗ trợ link SoundCloud hoặc YouTube",
        )
    await check_rate(f"oembed:{user.id}", limit=30)
    try:
        response = await drive_http.client().get(
            _OEMBED_ENDPOINTS[found[0]], params={"url": url, "format": "json"}
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không kết nối được tới SoundCloud/YouTube",
        ) from exc
    if response.status_code != 200 or len(response.content) > 100_000:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bài, hoặc bài đang để riêng tư",
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Dữ liệu trả về không hợp lệ",
        ) from exc
    author = str(data.get("author_name") or "")[:200]
    title = str(data.get("title") or "")[:300]
    # SoundCloud titles read "<track> by <uploader>"
    title = title.removesuffix(f" by {author}") if author else title
    thumbnail = data.get("thumbnail_url")
    return {
        "title": title,
        "author": author,
        "thumbnail_url": (
            thumbnail[:1000]
            if isinstance(thumbnail, str)
            and thumbnail.startswith("https://")
            # SoundCloud's stand-in logo for tracks without artwork
            and "/images/fb_placeholder" not in thumbnail
            else None
        ),
    }


@router.post("", response_model=ContentAdminRead, status_code=status.HTTP_201_CREATED)
async def create_content(
    data: ContentCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_editor),
) -> ContentAdminRead:
    content = await content_admin.create_content(session, data, user.id)
    await activity.log(
        session,
        actor=user,
        action=activity.CREATE,
        entity_type="content",
        entity_id=content.id,
        entity_title=content.title,
        detail={"type": content.type.value},
    )
    return ContentAdminRead.from_model(content)


@router.get("", response_model=Page[ContentAdminRead])
async def list_content(
    pagination: PaginationParams = Depends(),
    type: ContentType | None = None,
    content_status: ContentStatus | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_editor),
) -> Page[ContentAdminRead]:
    base = select(Content)
    if user.role == UserRole.author:
        base = base.where(Content.author_id == user.id)
    if type is not None:
        base = base.where(Content.type == type)
    if content_status is not None:
        base = base.where(Content.status == content_status)

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await session.scalars(
            base.options(
                selectinload(Content.media_links).selectinload(ContentMedia.media)
            )
            .order_by(Content.updated_at.desc(), Content.id.desc())
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
        )
    ).all()

    # Nạp email tác giả trong MỘT query (tránh N+1) rồi map vào từng item
    author_ids = {c.author_id for c in rows if c.author_id is not None}
    emails: dict[int, str] = {}
    if author_ids:
        emails = dict(
            (
                await session.execute(
                    select(User.id, User.email).where(User.id.in_(author_ids))
                )
            ).all()
        )

    items = []
    for c in rows:
        read = ContentAdminRead.from_model(c)
        read.author_email = emails.get(c.author_id) if c.author_id else None
        items.append(read)
    return Page.create(
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{content_id}", response_model=ContentAdminRead)
async def get_content(
    content_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_editor),
) -> ContentAdminRead:
    content = await _load(content_id, session)
    _ensure_can_edit(content, user)
    return ContentAdminRead.from_model(content)


@router.patch("/{content_id}", response_model=ContentAdminRead)
async def update_content(
    content_id: int,
    data: ContentUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_editor),
) -> ContentAdminRead:
    content = await _load(content_id, session, lock=True)
    _ensure_can_edit(content, user)
    # Chụp giá trị CŨ trước khi sửa -> log được "cũ → mới" cho tiêu đề
    if user.role == UserRole.author and content.status == ContentStatus.published:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Bài đã xuất bản cần biên tập viên chỉnh sửa; "
                "hãy tạo bản sao để đề xuất."
            ),
        )
    old_title = content.title
    updated = await content_admin.update_content(session, content, data)
    fields = sorted(data.model_dump(exclude_unset=True).keys())
    # Ghi rõ trường nào được sửa + diff tiêu đề -> admin biết chính xác thay đổi gì
    detail: dict = {"fields": fields}
    if "title" in fields and old_title != updated.title:
        detail["title_from"] = old_title
        detail["title_to"] = updated.title
    await activity.log(
        session,
        actor=user,
        action=activity.UPDATE,
        entity_type="content",
        entity_id=updated.id,
        entity_title=updated.title,
        detail=detail,
    )
    return ContentAdminRead.from_model(updated)


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(
    content_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_publisher),
) -> None:
    content = await _load(content_id, session, lock=True)
    # Chụp lại title/id/type TRƯỚC khi xóa để log còn đọc được
    title, cid, ctype = content.title, content.id, content.type.value
    await content_admin.delete_content(session, content)
    await activity.log(
        session,
        actor=user,
        action=activity.DELETE,
        entity_type="content",
        entity_id=cid,
        entity_title=title,
        detail={"type": ctype},
    )


@router.post("/{content_id}/publish", response_model=ContentAdminRead)
async def publish_content(
    content_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_publisher),
) -> ContentAdminRead:
    content = await _load(content_id, session, lock=True)
    published = await content_admin.publish(session, content)
    await activity.log(
        session,
        actor=user,
        action=activity.PUBLISH,
        entity_type="content",
        entity_id=published.id,
        entity_title=published.title,
    )
    return ContentAdminRead.from_model(published)


@router.post("/{content_id}/unpublish", response_model=ContentAdminRead)
async def unpublish_content(
    content_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_publisher),
) -> ContentAdminRead:
    content = await _load(content_id, session, lock=True)
    updated = await content_admin.set_status(session, content, ContentStatus.draft)
    await activity.log(
        session,
        actor=user,
        action=activity.UNPUBLISH,
        entity_type="content",
        entity_id=updated.id,
        entity_title=updated.title,
    )
    return ContentAdminRead.from_model(updated)


@router.post("/{content_id}/archive", response_model=ContentAdminRead)
async def archive_content(
    content_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_publisher),
) -> ContentAdminRead:
    content = await _load(content_id, session, lock=True)
    updated = await content_admin.set_status(session, content, ContentStatus.archived)
    await activity.log(
        session,
        actor=user,
        action=activity.ARCHIVE,
        entity_type="content",
        entity_id=updated.id,
        entity_title=updated.title,
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
    content = await _load(content_id, session, lock=True)
    _ensure_can_edit(content, user)
    copy = await content_admin.duplicate(session, content, user.id)
    await activity.log(
        session,
        actor=user,
        action=activity.DUPLICATE,
        entity_type="content",
        entity_id=copy.id,
        entity_title=copy.title,
        detail={"from_id": content.id},
    )
    return ContentAdminRead.from_model(copy)
