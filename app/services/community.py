"""Business logic tương tác cộng đồng: bình luận, cảm xúc, lưu bài."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Comment, PostReaction, SavedPost
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType, ReactionType
from app.models.user import User


def author_name(user: User | None) -> str:
    """Tên hiển thị của người bình luận (chưa có display_name -> lấy phần
    trước @ của email, KHÔNG lộ toàn bộ email)."""
    if user is None:
        return "Người dùng đã xoá"
    return user.email.split("@", 1)[0]


async def get_published_community(
    session: AsyncSession, content_id: int
) -> Content | None:
    """Chỉ cho tương tác trên bài cộng đồng ĐÃ publish."""
    return await session.scalar(
        select(Content).where(
            Content.id == content_id,
            Content.type == ContentType.community,
            Content.status == ContentStatus.published,
        )
    )


# ---- Bình luận ----
async def list_comments(
    session: AsyncSession, content_id: int, *, page: int, page_size: int
) -> tuple[list[Comment], int]:
    base = select(Comment).where(Comment.content_id == content_id)
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    stmt = (
        base.order_by(Comment.created_at.asc(), Comment.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await session.scalars(stmt)).all())
    return items, total or 0


async def create_comment(
    session: AsyncSession, content_id: int, user: User, body: str
) -> Comment:
    comment = Comment(content_id=content_id, user_id=user.id, body=body)
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    return comment


async def comment_count(session: AsyncSession, content_id: int) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(Comment)
            .where(Comment.content_id == content_id)
        )
    ) or 0


# ---- Cảm xúc ----
async def reaction_counts(session: AsyncSession, content_id: int) -> dict[str, int]:
    rows = await session.execute(
        select(PostReaction.type, func.count())
        .where(PostReaction.content_id == content_id)
        .group_by(PostReaction.type)
    )
    return {str(t): int(n) for t, n in rows.all()}


async def my_reaction(
    session: AsyncSession, content_id: int, user_id: int
) -> ReactionType | None:
    return await session.scalar(
        select(PostReaction.type).where(
            PostReaction.content_id == content_id,
            PostReaction.user_id == user_id,
        )
    )


async def set_reaction(
    session: AsyncSession, content_id: int, user_id: int, type_: ReactionType
) -> None:
    existing = await session.scalar(
        select(PostReaction).where(
            PostReaction.content_id == content_id,
            PostReaction.user_id == user_id,
        )
    )
    if existing:
        existing.type = type_
    else:
        session.add(PostReaction(content_id=content_id, user_id=user_id, type=type_))
    await session.commit()


async def remove_reaction(session: AsyncSession, content_id: int, user_id: int) -> None:
    await session.execute(
        delete(PostReaction).where(
            PostReaction.content_id == content_id,
            PostReaction.user_id == user_id,
        )
    )
    await session.commit()


# ---- Lưu bài ----
async def is_saved(session: AsyncSession, content_id: int, user_id: int) -> bool:
    return (
        await session.scalar(
            select(func.count())
            .select_from(SavedPost)
            .where(
                SavedPost.content_id == content_id,
                SavedPost.user_id == user_id,
            )
        )
    ) > 0


async def save_post(session: AsyncSession, content_id: int, user_id: int) -> None:
    if not await is_saved(session, content_id, user_id):
        session.add(SavedPost(content_id=content_id, user_id=user_id))
        await session.commit()


async def unsave_post(session: AsyncSession, content_id: int, user_id: int) -> None:
    await session.execute(
        delete(SavedPost).where(
            SavedPost.content_id == content_id,
            SavedPost.user_id == user_id,
        )
    )
    await session.commit()
