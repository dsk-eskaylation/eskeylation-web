"""Đóng góp lời bài hát — user gửi, admin duyệt (không ghi đè trực tiếp)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import get_current_user
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType
from app.models.lyrics import LyricSuggestion
from app.models.user import User
from app.services.ratelimit import check_rate
from app.services.sanitize import sanitize_summary

router = APIRouter(prefix="/api/music", tags=["lyrics"])


class LyricIn(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class LyricAck(BaseModel):
    ok: bool = True
    message: str


@router.post(
    "/{content_id}/lyrics",
    response_model=LyricAck,
    status_code=status.HTTP_201_CREATED,
)
async def submit_lyrics(
    content_id: int,
    payload: LyricIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LyricAck:
    music = await session.scalar(
        select(Content).where(
            Content.id == content_id,
            Content.type == ContentType.music,
            Content.status == ContentStatus.published,
        )
    )
    if music is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài hát"
        )
    await check_rate(f"lyrics:{user.id}", limit=5, window_seconds=300)
    body = sanitize_summary(payload.body) or ""
    if not body.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Nội dung lời trống",
        )
    session.add(
        LyricSuggestion(content_id=content_id, user_id=user.id, body=body)
    )
    await session.commit()
    return LyricAck(message="Cảm ơn đóng góp! Lời sẽ hiển thị sau khi được duyệt.")
