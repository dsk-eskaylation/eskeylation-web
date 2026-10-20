"""Review contributions and update the mapped CMS song in one transaction."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.db import get_session
from app.dependencies import PaginationParams, require_role
from app.models.activity import ActivityLog
from app.models.content import Content
from app.models.enums import ContentType, UserRole
from app.models.interaction_target import InteractionTarget
from app.models.lyrics import LyricSuggestion
from app.models.user import User
from app.schemas.lyrics import LyricReview, LyricStatus, LyricSuggestionOut
from app.schemas.pagination import Page
from app.services import moderation

router = APIRouter(prefix="/admin/moderation/lyrics", tags=["moderation"])
Session = Annotated[AsyncSession, Depends(get_session)]
Admin = Annotated[User, Depends(require_role(UserRole.admin))]
Pagination = Annotated[PaginationParams, Depends()]


def _query():
    return (
        select(LyricSuggestion, Content.id, Content.title, Content.type)
        .outerjoin(
            InteractionTarget, InteractionTarget.id == LyricSuggestion.content_id
        )
        .outerjoin(Content, Content.id == InteractionTarget.content_id)
    )


def _out(row) -> LyricSuggestionOut:
    suggestion, cms_id, title, type_ = row
    return LyricSuggestionOut(
        id=suggestion.id,
        content_id=suggestion.content_id,
        cms_content_id=cms_id,
        title=title,
        user_email=suggestion.user.email if suggestion.user else None,
        body=suggestion.body,
        status=suggestion.status,
        created_at=suggestion.created_at,
        can_accept=cms_id is not None and type_ == ContentType.music,
    )


@router.get("")
async def list_lyrics(
    session: Session,
    _: Admin,
    pagination: Pagination,
    review_status: LyricStatus = "pending",
) -> Page[LyricSuggestionOut]:
    condition = LyricSuggestion.status == review_status
    total = await session.scalar(
        select(func.count()).select_from(LyricSuggestion).where(condition)
    )
    rows = await session.execute(
        _query()
        .where(condition)
        .order_by(LyricSuggestion.created_at.desc(), LyricSuggestion.id.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    return Page.create(
        items=[_out(row) for row in rows.unique()],
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.patch("/{suggestion_id}")
async def review_lyrics(
    suggestion_id: int, payload: LyricReview, session: Session, user: Admin
) -> LyricSuggestionOut:
    # Lock this contribution so two admins cannot accept/reject it concurrently.
    suggestion = await session.scalar(
        select(LyricSuggestion)
        .options(lazyload(LyricSuggestion.user))
        .where(LyricSuggestion.id == suggestion_id)
        .with_for_update(of=LyricSuggestion)
    )
    if suggestion is None:
        raise HTTPException(404, "Không tìm thấy đóng góp lời nhạc")
    if suggestion.status != "pending":
        raise HTTPException(409, "Đóng góp này đã được xử lý. Hãy tải lại danh sách.")

    content = await session.scalar(
        select(Content)
        .join(InteractionTarget, InteractionTarget.content_id == Content.id)
        .where(
            InteractionTarget.id == suggestion.content_id,
            Content.type == ContentType.music,
        )
        .with_for_update(of=Content)
    )
    if payload.status == "accepted":
        if content is None:
            raise HTTPException(409, "Bài hát chưa liên kết với CMS hoặc đã bị xóa")
        await moderation.assert_clean(session, body={"lyrics": suggestion.body})
        content.body = {**content.body, "lyrics": suggestion.body}
    suggestion.status = payload.status
    session.add(
        ActivityLog(
            actor_id=user.id,
            actor_email=user.email,
            action="lyrics_accept" if payload.status == "accepted" else "lyrics_reject",
            entity_type="lyric_suggestion",
            entity_id=suggestion.id,
            entity_title=content.title if content else None,
            detail={
                "content_id": suggestion.content_id,
                "cms_content_id": content.id if content else None,
            },
        )
    )
    await session.flush()
    # Build the response while locks still protect the song and suggestion.
    row = (
        (
            await session.execute(
                _query()
                .where(LyricSuggestion.id == suggestion_id)
                .execution_options(populate_existing=True)
            )
        )
        .unique()
        .one()
    )
    result = _out(row)
    await session.commit()
    return result
