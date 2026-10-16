"""Kiểm duyệt (CHỈ admin): quản lý từ cấm + xoá bình luận không phù hợp."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_role
from app.models.community import Comment
from app.models.enums import UserRole
from app.models.moderation import BannedWord
from app.models.user import User
from app.schemas.moderation import BannedWordIn, BannedWordOut
from app.services import activity, moderation

router = APIRouter(prefix="/admin/moderation", tags=["moderation"])

_admin = require_role(UserRole.admin)


# ---- Từ cấm ----
@router.get("/banned-words", response_model=list[BannedWordOut])
async def list_banned_words(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_admin),
) -> list[BannedWordOut]:
    rows = await session.scalars(select(BannedWord).order_by(BannedWord.word))
    return [BannedWordOut.model_validate(w, from_attributes=True) for w in rows]


@router.post(
    "/banned-words", response_model=BannedWordOut, status_code=status.HTTP_201_CREATED
)
async def add_banned_word(
    data: BannedWordIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_admin),
) -> BannedWordOut:
    word = data.word.strip().lower()
    if not word:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Từ trống"
        )
    entry = BannedWord(word=word)
    session.add(entry)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Từ đã có trong danh sách"
        ) from exc
    await session.refresh(entry)
    moderation.invalidate()  # cache nạp lại -> từ mới có hiệu lực ngay
    await activity.log(
        session,
        actor=user,
        action=activity.BANNED_ADD,
        entity_type="banned_word",
        entity_id=entry.id,
        entity_title=word,
    )
    return BannedWordOut.model_validate(entry, from_attributes=True)


@router.delete("/banned-words/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_banned_word(
    word_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_admin),
) -> None:
    entry = await session.get(BannedWord, word_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy từ"
        )
    word = entry.word
    await session.delete(entry)
    await session.commit()
    moderation.invalidate()
    await activity.log(
        session,
        actor=user,
        action=activity.BANNED_REMOVE,
        entity_type="banned_word",
        entity_id=word_id,
        entity_title=word,
    )


# ---- Bình luận (xoá bình luận không phù hợp) ----
@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_admin),
) -> None:
    comment = await session.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bình luận"
        )
    snippet = (comment.body or "")[:80]
    await session.delete(comment)
    await session.commit()
    await activity.log(
        session,
        actor=user,
        action=activity.COMMENT_DELETE,
        entity_type="comment",
        entity_id=comment_id,
        entity_title=snippet,
    )
