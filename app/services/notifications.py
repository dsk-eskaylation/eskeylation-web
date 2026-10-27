"""Tạo / đọc thông báo tương tác. Best-effort: lỗi ghi thông báo không làm hỏng
thao tác chính (cảm xúc/bình luận đã commit trước đó)."""

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.community import Comment
from app.models.content import Content
from app.models.interaction_target import InteractionTarget
from app.models.notification import Notification
from app.models.user import User

logger = logging.getLogger(__name__)


async def post_author(session: AsyncSession, content_id: int) -> int | None:
    return await session.scalar(
        select(Content.author_id)
        .join(InteractionTarget, InteractionTarget.content_id == Content.id)
        .where(InteractionTarget.id == content_id)
    )


async def comment_author(session: AsyncSession, comment_id: int) -> int | None:
    return await session.scalar(select(Comment.user_id).where(Comment.id == comment_id))


async def notify(
    session: AsyncSession,
    *,
    recipient_id: int | None,
    actor: User,
    kind: str,
    content_id: int,
    comment_id: int | None = None,
) -> None:
    if recipient_id is None or recipient_id == actor.id:
        return
    same = (
        Notification.user_id == recipient_id,
        Notification.actor_id == actor.id,
        Notification.kind == kind,
        Notification.content_id == content_id,
        Notification.comment_id.is_(None)
        if comment_id is None
        else Notification.comment_id == comment_id,
    )
    try:
        # Đổi/bật lại cảm xúc chỉ giữ một thông báo mới nhất, không spam.
        if kind != "post_comment":
            await session.execute(delete(Notification).where(*same))
        session.add(
            Notification(
                user_id=recipient_id,
                actor_id=actor.id,
                kind=kind,
                content_id=content_id,
                comment_id=comment_id,
            )
        )
        await session.commit()
    except Exception:
        logger.warning("Ghi thông báo thất bại (%s %s)", kind, content_id)
        await session.rollback()


async def list_for(session: AsyncSession, user_id: int, limit: int = 30) -> dict:
    actor = aliased(User)
    rows = (
        await session.execute(
            select(Notification, actor.email, Content.title, Content.slug, Content.type)
            .outerjoin(actor, actor.id == Notification.actor_id)
            .join(InteractionTarget, InteractionTarget.id == Notification.content_id)
            .outerjoin(Content, Content.id == InteractionTarget.content_id)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit)
        )
    ).all()
    unread = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    return {
        "unread": unread or 0,
        "items": [
            {
                "id": n.id,
                "kind": n.kind,
                "actor_name": email.split("@", 1)[0] if email else "Người dùng đã xoá",
                "content_id": n.content_id,
                "content_title": title,
                "content_slug": slug,
                "content_type": type_,
                "comment_id": n.comment_id,
                "read": n.read_at is not None,
                "created_at": n.created_at,
            }
            for n, email, title, slug, type_ in rows
        ],
    }


async def mark_all_read(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await session.commit()
