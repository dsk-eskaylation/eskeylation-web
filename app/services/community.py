"""Business logic tương tác cộng đồng: bình luận, cảm xúc, lưu bài.

Vì DB ở xa (Supabase), chi phí chính là ROUND-TRIP mạng chứ không phải query —
các hàm đọc tổng hợp đều gộp nhiều thống kê vào MỘT câu SQL (scalar subquery /
GROUP BY + bool_or) thay vì nhiều câu tuần tự.
"""

import json

from fastapi import HTTPException
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.community import (
    Comment,
    CommentReaction,
    PostReaction,
    SavedPost,
)
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType, ReactionType
from app.models.interaction_target import InteractionTarget
from app.models.media import ContentMedia, Media
from app.models.user import User
from app.schemas.public import ContentOut
from app.services.interaction_targets import (
    drive_content,
    ensure_drive_target,
    published_cms_target,
)


def author_name(user: User | None) -> str:
    """Tên hiển thị của người bình luận (chưa có display_name -> lấy phần
    trước @ của email, KHÔNG lộ toàn bộ email)."""
    if user is None:
        return "Người dùng đã xoá"
    return user.email.split("@", 1)[0]


# Bài nhạc dùng chung bình luận / cảm xúc / lưu (= yêu thích) với bài cộng đồng.
INTERACTIVE_TYPES = (ContentType.community, ContentType.music)


async def get_published_community(
    session: AsyncSession, content_id: int
) -> Content | ContentOut | None:
    """Chỉ cho tương tác trên bài cộng đồng hoặc bài nhạc ĐÃ publish."""
    for type_ in INTERACTIVE_TYPES:
        if get_settings().public_content_source == "drive":
            post = await drive_content(content_id, type_)
            if post is not None:
                await ensure_drive_target(session, post)
                return post
        elif post := await published_cms_target(session, content_id, type_):
            return post
    return None


async def interaction_overview(
    session: AsyncSession, content_id: int, user_id: int | None
) -> dict | None:
    """Toàn bộ tổng quan tương tác 1 bài trong MỘT round-trip:
    tồn tại + đếm cảm xúc theo loại + cảm xúc của tôi + số bình luận + đã lưu.
    Trả None nếu bài không tồn tại/chưa publish."""
    is_drive = get_settings().public_content_source == "drive"
    if content_id == 0 or abs(content_id) > 2**53 - 1:
        return None
    if is_drive and await get_published_community(session, content_id) is None:
        return None
    row = (
        await session.execute(
            text(
                """
                SELECT
                  (:is_drive OR EXISTS(SELECT 1 FROM interaction_targets t
                         JOIN contents c ON c.id=t.content_id
                         WHERE t.id=CAST(:cid AS bigint)
                           AND c.type IN ('community', 'music')
                           AND c.status='published'))
                    AS ok,
                  (SELECT coalesce(jsonb_object_agg(t.type, t.n), '{}'::jsonb)
                     FROM (SELECT type, count(*) AS n FROM post_reactions
                           WHERE content_id=:cid GROUP BY type) t) AS counts,
                  (SELECT type FROM post_reactions
                    WHERE content_id=:cid AND user_id=:uid) AS mine,
                  (SELECT count(*) FROM comments WHERE content_id=:cid)
                    AS comment_count,
                  EXISTS(SELECT 1 FROM saved_posts
                         WHERE content_id=:cid AND user_id=:uid) AS saved
                """
            ),
            {
                "cid": content_id,
                "uid": user_id if user_id is not None else -1,
                "is_drive": is_drive,
            },
        )
    ).one()
    if not row.ok:
        return None
    counts = row.counts if isinstance(row.counts, dict) else json.loads(row.counts)
    return {
        "counts": counts,
        "total": sum(counts.values()),
        "mine": row.mine,
        "comment_count": row.comment_count,
        "saved": row.saved,
    }


# ---- Bình luận ----
async def list_comments(
    session: AsyncSession,
    content_id: int,
    *,
    page: int,
    page_size: int,
    after_id: int | None = None,
) -> tuple[list[Comment], int]:
    # Gộp ĐẾM TỔNG vào cùng query lấy dữ liệu (window count) — bớt 1 round-trip
    stmt = (
        select(Comment, func.count().over().label("total"))
        .where(Comment.content_id == content_id)
        .order_by(Comment.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if after_id is not None:
        stmt = stmt.where(Comment.id > after_id)
    rows = (await session.execute(stmt)).unique().all()
    items = [r[0] for r in rows]
    if rows:
        total = rows[0].total
    elif page > 1:
        # Trang vượt phạm vi (hiếm) -> đếm lại để total vẫn đúng
        total = (
            await session.scalar(
                select(func.count())
                .select_from(Comment)
                .where(Comment.content_id == content_id)
            )
        ) or 0
    else:
        total = 0
    return items, total


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


async def get_comment(session: AsyncSession, comment_id: int) -> Comment | None:
    return await session.get(Comment, comment_id)


async def update_comment_body(
    session: AsyncSession, comment: Comment, body: str
) -> Comment:
    comment.body = body
    await session.commit()
    await session.refresh(comment)
    return comment


async def delete_comment(session: AsyncSession, comment: Comment) -> None:
    await session.delete(comment)
    await session.commit()


# ---- Cảm xúc trên BÌNH LUẬN ----
async def comment_reactions_bulk(
    session: AsyncSession, comment_ids: list[int], user_id: int | None
) -> dict[int, tuple[dict[str, int], int, ReactionType | None]]:
    """Nạp gọn (counts, total, my_reaction) cho NHIỀU bình luận trong MỘT query
    (GROUP BY + bool_or đánh dấu nhóm chứa cảm xúc của tôi) -> tránh N+1."""
    result: dict[int, tuple[dict[str, int], int, ReactionType | None]] = {
        cid: ({}, 0, None) for cid in comment_ids
    }
    if not comment_ids:
        return result
    uid = user_id if user_id is not None else -1
    rows = await session.execute(
        select(
            CommentReaction.comment_id,
            CommentReaction.type,
            func.count(),
            func.bool_or(CommentReaction.user_id == uid),
        )
        .where(CommentReaction.comment_id.in_(comment_ids))
        .group_by(CommentReaction.comment_id, CommentReaction.type)
    )
    for cid, rtype, n, includes_me in rows.all():
        counts, total, mine = result[cid]
        counts[str(rtype)] = int(n)
        result[cid] = (counts, total + int(n), rtype if includes_me else mine)
    return result


async def comment_reaction_summary(
    session: AsyncSession, comment_id: int, user_id: int | None
) -> tuple[dict[str, int], int, ReactionType | None]:
    return (await comment_reactions_bulk(session, [comment_id], user_id))[comment_id]


async def set_comment_reaction(
    session: AsyncSession, comment_id: int, user_id: int, type_: ReactionType
) -> None:
    # UPSERT một phát (thay cho SELECT rồi INSERT/UPDATE) — bớt 1 round-trip
    stmt = pg_insert(CommentReaction).values(
        comment_id=comment_id, user_id=user_id, type=type_
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_comment_reaction_user_comment", set_={"type": type_}
    )
    await session.execute(stmt)
    await session.commit()


async def remove_comment_reaction(
    session: AsyncSession, comment_id: int, user_id: int
) -> None:
    await session.execute(
        delete(CommentReaction).where(
            CommentReaction.comment_id == comment_id,
            CommentReaction.user_id == user_id,
        )
    )
    await session.commit()


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


async def reaction_summary(
    session: AsyncSession, content_id: int, user_id: int | None
) -> tuple[dict[str, int], int, str | None]:
    """(counts, total, my_reaction) trong MỘT query: GROUP BY type +
    bool_or(user_id = :uid) đánh dấu nhóm chứa cảm xúc của tôi."""
    rows = (
        await session.execute(
            text(
                "SELECT type, count(*) AS n, bool_or(user_id = :uid) AS me "
                "FROM post_reactions WHERE content_id = :cid GROUP BY type"
            ),
            {"cid": content_id, "uid": user_id if user_id is not None else -1},
        )
    ).all()
    counts = {str(t): int(n) for t, n, _ in rows}
    mine = next((str(t) for t, _, me in rows if me), None)
    return counts, sum(counts.values()), mine


async def set_reaction(
    session: AsyncSession, content_id: int, user_id: int, type_: ReactionType
) -> None:
    # UPSERT một phát (thay cho SELECT rồi INSERT/UPDATE) — bớt 1 round-trip
    stmt = pg_insert(PostReaction).values(
        content_id=content_id, user_id=user_id, type=type_
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_reaction_user_content", set_={"type": type_}
    )
    await session.execute(stmt)
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
    await session.execute(
        pg_insert(SavedPost)
        .values(content_id=content_id, user_id=user_id)
        .on_conflict_do_nothing()
    )
    await session.commit()


async def unsave_post(session: AsyncSession, content_id: int, user_id: int) -> None:
    await session.execute(
        delete(SavedPost).where(
            SavedPost.content_id == content_id,
            SavedPost.user_id == user_id,
        )
    )
    await session.commit()


async def list_saved(
    session: AsyncSession, user_id: int, type_: ContentType, page: int, page_size: int
) -> tuple[list[Content | ContentOut], int]:
    """Bài đã lưu (cộng đồng) / bài hát yêu thích (nhạc) của user, mới lưu trước."""
    if get_settings().public_content_source == "drive":
        ids = (
            await session.scalars(
                select(SavedPost.content_id)
                .where(SavedPost.user_id == user_id, SavedPost.content_id < 0)
                .order_by(SavedPost.created_at.desc())
            )
        ).all()
        # shortcut: resolves every saved Drive id per request; page in SQL if lists grow
        found = [await drive_content(i, type_) for i in ids]
        items = [c for c in found if c is not None]
        return items[(page - 1) * page_size : page * page_size], len(items)
    base = (
        select(Content)
        .join(InteractionTarget, InteractionTarget.content_id == Content.id)
        .join(SavedPost, SavedPost.content_id == InteractionTarget.id)
        .where(
            SavedPost.user_id == user_id,
            Content.type == type_,
            Content.status == ContentStatus.published,
        )
    )
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = await session.scalars(
        base.options(selectinload(Content.media_links).joinedload(ContentMedia.media))
        .order_by(SavedPost.created_at.desc(), SavedPost.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.all()), total or 0


async def list_authored(session: AsyncSession, user_id: int) -> list[Content]:
    rows = await session.scalars(
        select(Content)
        .where(
            Content.author_id == user_id,
            Content.type == ContentType.community,
            Content.status != ContentStatus.archived,
        )
        .options(selectinload(Content.media_links).joinedload(ContentMedia.media))
        .order_by(Content.created_at.desc())
        .limit(100)
    )
    return list(rows.all())


async def ensure_own_unused_images(
    session: AsyncSession, media_ids: list[int], user_id: int
) -> None:
    """Thành viên chỉ gắn được ảnh chính mình vừa tải và chưa thuộc bài nào."""
    if not media_ids:
        return
    ok = await session.scalar(
        select(func.count())
        .select_from(Media)
        .where(
            Media.id.in_(media_ids),
            Media.uploaded_by == user_id,
            Media.mime_type.startswith("image/"),
            ~select(ContentMedia.id).where(ContentMedia.media_id == Media.id).exists(),
        )
    )
    if ok != len(media_ids):
        raise HTTPException(422, "Ảnh không hợp lệ hoặc không phải ảnh bạn tải lên")
