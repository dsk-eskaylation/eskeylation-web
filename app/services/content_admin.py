"""Business logic CMS: tạo/sửa/workflow nội dung, gắn media, validate publish."""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Content
from app.models.enums import ContentStatus, ContentType
from app.models.media import ContentMedia, Media
from app.schemas.admin import ContentCreate, ContentMediaIn, ContentUpdate
from app.services import moderation
from app.services.sanitize import sanitize_body, sanitize_summary, validate_embeds
from app.services.slug import unique_slug


async def get_with_media(session: AsyncSession, content_id: int) -> Content | None:
    stmt = (
        select(Content)
        .where(Content.id == content_id)
        .options(selectinload(Content.media_links).selectinload(ContentMedia.media))
    )
    return await session.scalar(stmt)


def _validate_media_in(media_in: list[ContentMediaIn]) -> None:
    """Chặn input vi phạm constraint DB (trùng media, >1 primary) bằng 422
    thay vì để IntegrityError nổ thành 500."""
    ids = [m.media_id for m in media_in]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Media gắn trùng trong 1 nội dung: {dup}",
        )
    primaries = sum(1 for m in media_in if m.is_primary)
    if primaries > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Chỉ được tối đa 1 media primary mỗi nội dung",
        )


async def _replace_media(
    session: AsyncSession, content: Content, media_in: list[ContentMediaIn]
) -> None:
    _validate_media_in(media_in)
    if media_in:
        ids = [m.media_id for m in media_in]
        found = set(
            (await session.scalars(select(Media.id).where(Media.id.in_(ids)))).all()
        )
        missing = sorted(set(ids) - found)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Media không tồn tại: {missing}",
            )
    await session.execute(
        delete(ContentMedia).where(ContentMedia.content_id == content.id)
    )
    # Chuẩn hoá position về 0..n-1 theo thứ tự client yêu cầu — thỏa
    # UNIQUE(content_id, position) mà vẫn giữ đúng ý đồ sắp xếp.
    for pos, m in enumerate(sorted(media_in, key=lambda x: x.position)):
        session.add(
            ContentMedia(
                content_id=content.id,
                media_id=m.media_id,
                caption=m.caption,
                position=pos,
                is_primary=m.is_primary,
            )
        )


async def create_content(
    session: AsyncSession, data: ContentCreate, author_id: int
) -> Content:
    validate_embeds(data.body)
    # Chặn từ ngữ không phù hợp trong mô tả + body (kiểm duyệt)
    await moderation.assert_clean(session, summary=data.summary, body=data.body)
    content = Content(
        type=data.type,
        title=data.title,
        slug=await unique_slug(session, data.title, data.type),
        summary=sanitize_summary(data.summary),
        body=sanitize_body(data.body),
        status=ContentStatus.draft,
        author_id=author_id,
    )
    session.add(content)
    try:
        await session.flush()
        await _replace_media(session, content, data.media)
        await session.commit()
    except IntegrityError as exc:
        # Hai request cùng title đua nhau qua unique_slug -> UNIQUE(type, slug)
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slug vừa bị chiếm bởi thao tác khác — thử lại",
        ) from exc
    return await get_with_media(session, content.id)


async def update_content(
    session: AsyncSession, content: Content, data: ContentUpdate
) -> Content:
    fields = data.model_dump(exclude_unset=True)
    # Chặn từ ngữ không phù hợp trong các trường được sửa (kiểm duyệt)
    await moderation.assert_clean(
        session,
        summary=fields.get("summary") if "summary" in fields else None,
        body=fields.get("body") if "body" in fields else None,
    )
    if "title" in fields:
        content.title = fields["title"]
    if "summary" in fields:
        content.summary = sanitize_summary(fields["summary"])
    if "body" in fields:
        validate_embeds(fields["body"])
        content.body = sanitize_body(fields["body"])
    if "media" in fields:
        await _replace_media(session, content, data.media or [])
    await session.commit()
    # expire_on_commit=False giữ media_links cũ trên object -> ép reload cho đúng
    session.expire(content, ["media_links"])
    return await get_with_media(session, content.id)


async def delete_content(session: AsyncSession, content: Content) -> None:
    await session.delete(content)
    await session.commit()


def validate_for_publish(content: Content) -> None:
    """Chặn publish nếu thiếu media/metadata bắt buộc theo loại."""
    errors: list[str] = []
    if content.type == ContentType.music and not content.body.get("artist"):
        errors.append("music cần 'artist' trong body")
    if content.type == ContentType.gallery and not content.media_links:
        errors.append("gallery cần ít nhất 1 media")
    if content.type == ContentType.homepage and not content.body.get("sections"):
        errors.append("homepage cần 'sections' trong body")
    if content.type == ContentType.community and not (
        content.title and content.summary
    ):
        errors.append("community cần title và summary")
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="; ".join(errors),
        )


async def publish(session: AsyncSession, content: Content) -> Content:
    validate_for_publish(content)
    content.status = ContentStatus.published
    if content.published_at is None:
        content.published_at = datetime.now(UTC)
    await session.commit()
    return await get_with_media(session, content.id)


async def set_status(
    session: AsyncSession, content: Content, new_status: ContentStatus
) -> Content:
    # Chuyển sang published PHẢI qua publish() để validate + set published_at
    # (lưới an toàn cho CHECK ck_contents_published_at — db-review M1).
    if new_status == ContentStatus.published:
        return await publish(session, content)
    content.status = new_status
    await session.commit()
    return await get_with_media(session, content.id)


async def duplicate(session: AsyncSession, content: Content, author_id: int) -> Content:
    copy = Content(
        type=content.type,
        title=f"{content.title} (copy)",
        slug=await unique_slug(session, f"{content.title} copy", content.type),
        summary=content.summary,
        body=dict(content.body),
        status=ContentStatus.draft,
        author_id=author_id,
    )
    session.add(copy)
    try:
        await session.flush()
        for link in content.media_links:
            session.add(
                ContentMedia(
                    content_id=copy.id,
                    media_id=link.media_id,
                    caption=link.caption,
                    position=link.position,
                    is_primary=link.is_primary,
                )
            )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slug vừa bị chiếm bởi thao tác khác — thử lại",
        ) from exc
    return await get_with_media(session, copy.id)
