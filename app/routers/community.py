"""Tương tác cộng đồng: bình luận (realtime WebSocket), cảm xúc, lưu bài.

Chỉ user đã đăng nhập mới tạo/đổi tương tác (dependency get_current_user).
Xem (GET) + nhận realtime (WS) là công khai. Bình luận realtime broadcast qua
Redis pub/sub (app.services.realtime).
"""

import asyncio

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import SessionLocal, get_session
from app.dependencies import (
    PaginationParams,
    get_current_user,
    get_current_user_optional,
)
from app.models.enums import ReactionType
from app.models.user import User
from app.schemas.community import (
    CommentIn,
    CommentOut,
    CommentUpdate,
    InteractionOut,
    ReactionIn,
    ReactionSummary,
)
from app.schemas.pagination import Page
from app.services import community, moderation, realtime
from app.services.ratelimit import check_rate
from app.services.sanitize import sanitize_summary

settings = get_settings()

router = APIRouter(prefix="/api/community", tags=["community"])


async def _ensure_post(session: AsyncSession, content_id: int) -> None:
    if await community.get_published_community(session, content_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bài cộng đồng",
        )


def _comment_out(
    c,
    *,
    reactions: tuple[dict[str, int], int, ReactionType | None] | None = None,
    is_mine: bool = False,
) -> CommentOut:
    counts, total, mine = reactions or ({}, 0, None)
    # edited khi updated_at khác created_at. Lúc tạo, cả hai = now() trong CÙNG
    # transaction nên BẰNG NHAU chính xác; chỉ update_comment_body mới đổi
    # updated_at (reaction là bảng riêng, không đụng comment) -> so sánh khác nhau
    # là đủ tin cậy, không cần ngưỡng thời gian.
    edited = bool(c.updated_at and c.created_at and c.updated_at != c.created_at)
    return CommentOut(
        id=c.id,
        content_id=c.content_id,
        body=c.body,
        author_name=community.author_name(c.user),
        created_at=c.created_at,
        updated_at=c.updated_at,
        edited=edited,
        reactions=ReactionSummary(counts=counts, total=total, my_reaction=mine),
        is_mine=is_mine,
    )


async def _load_owned_comment(
    session: AsyncSession, content_id: int, comment_id: int, user: User
):
    """Nạp bình luận và đảm bảo thuộc bài + thuộc user hiện tại (chống IDOR)."""
    comment = await community.get_comment(session, comment_id)
    if comment is None or comment.content_id != content_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bình luận"
        )
    if comment.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ thao tác được trên bình luận của mình",
        )
    return comment


async def _summary(
    session: AsyncSession, content_id: int, user: User | None
) -> ReactionSummary:
    counts, total, mine = await community.reaction_summary(
        session, content_id, user.id if user else None
    )
    return ReactionSummary(counts=counts, total=total, my_reaction=mine)


# ---- Tổng quan ----
@router.get("/{content_id}/interactions", response_model=InteractionOut)
async def get_interactions(
    content_id: int,
    user: User | None = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_session),
) -> InteractionOut:
    # MỘT round-trip: tồn tại + cảm xúc + của tôi + số bình luận + đã lưu
    data = await community.interaction_overview(
        session, content_id, user.id if user else None
    )
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bài cộng đồng",
        )
    return InteractionOut(
        content_id=content_id,
        reactions=ReactionSummary(
            counts=data["counts"], total=data["total"], my_reaction=data["mine"]
        ),
        comment_count=data["comment_count"],
        saved=data["saved"],
    )


# ---- Bình luận ----
@router.get("/{content_id}/comments", response_model=Page[CommentOut])
async def list_comments(
    content_id: int,
    pagination: PaginationParams = Depends(),
    user: User | None = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_session),
) -> Page[CommentOut]:
    await _ensure_post(session, content_id)
    items, total = await community.list_comments(
        session, content_id, page=pagination.page, page_size=pagination.page_size
    )
    # Nạp gọn cảm xúc cho cả trang trong 2 query (tránh N+1)
    reactions = await community.comment_reactions_bulk(
        session, [c.id for c in items], user.id if user else None
    )
    return Page.create(
        items=[
            _comment_out(
                c,
                reactions=reactions.get(c.id),
                is_mine=bool(user and c.user_id == user.id),
            )
            for c in items
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "/{content_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    content_id: int,
    payload: CommentIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CommentOut:
    await _ensure_post(session, content_id)
    await check_rate(f"comment:{user.id}", limit=10, window_seconds=60)
    body = sanitize_summary(payload.body) or ""
    if not body.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Nội dung bình luận trống",
        )
    # Chặn bình luận chứa từ ngữ không phù hợp (kiểm duyệt)
    await moderation.assert_clean(session, text=body)
    comment = await community.create_comment(session, content_id, user, body)
    out = _comment_out(comment, is_mine=True)
    # Broadcast bản KHÔNG kèm is_mine cho người khác (is_mine tính theo mỗi client)
    await realtime.publish(
        content_id,
        {
            "kind": "comment",
            "comment": _comment_out(comment).model_dump(mode="json"),
        },
    )
    return out


@router.patch("/{content_id}/comments/{comment_id}", response_model=CommentOut)
async def edit_comment(
    content_id: int,
    comment_id: int,
    payload: CommentUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CommentOut:
    await _ensure_post(session, content_id)
    comment = await _load_owned_comment(session, content_id, comment_id, user)
    body = sanitize_summary(payload.body) or ""
    if not body.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Nội dung bình luận trống",
        )
    await moderation.assert_clean(session, text=body)
    updated = await community.update_comment_body(session, comment, body)
    reactions = await community.comment_reaction_summary(session, comment_id, user.id)
    await realtime.publish(
        content_id,
        {
            "kind": "comment_edit",
            "comment": _comment_out(updated).model_dump(mode="json"),
        },
    )
    return _comment_out(updated, reactions=reactions, is_mine=True)


@router.delete(
    "/{content_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_comment(
    content_id: int,
    comment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _ensure_post(session, content_id)
    comment = await _load_owned_comment(session, content_id, comment_id, user)
    await community.delete_comment(session, comment)
    await realtime.publish(
        content_id, {"kind": "comment_delete", "comment_id": comment_id}
    )


# ---- Cảm xúc trên BÌNH LUẬN ----
@router.put(
    "/{content_id}/comments/{comment_id}/reaction", response_model=ReactionSummary
)
async def react_comment(
    content_id: int,
    comment_id: int,
    payload: ReactionIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReactionSummary:
    await _ensure_post(session, content_id)
    comment = await community.get_comment(session, comment_id)
    if comment is None or comment.content_id != content_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bình luận"
        )
    await check_rate(f"creact:{user.id}", limit=40, window_seconds=60)
    await community.set_comment_reaction(session, comment_id, user.id, payload.type)
    counts, total, mine = await community.comment_reaction_summary(
        session, comment_id, user.id
    )
    return ReactionSummary(counts=counts, total=total, my_reaction=mine)


@router.delete(
    "/{content_id}/comments/{comment_id}/reaction", response_model=ReactionSummary
)
async def unreact_comment(
    content_id: int,
    comment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReactionSummary:
    await _ensure_post(session, content_id)
    await check_rate(f"creact:{user.id}", limit=40, window_seconds=60)
    await community.remove_comment_reaction(session, comment_id, user.id)
    counts, total, mine = await community.comment_reaction_summary(
        session, comment_id, user.id
    )
    return ReactionSummary(counts=counts, total=total, my_reaction=mine)


# ---- Cảm xúc ----
@router.put("/{content_id}/reaction", response_model=ReactionSummary)
async def set_reaction(
    content_id: int,
    payload: ReactionIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReactionSummary:
    await _ensure_post(session, content_id)
    # Rate-limit: mỗi reaction ghi DB + broadcast realtime cho mọi người xem bài
    # -> chặn spam toggle gây khuếch đại broadcast (DoS tầng ứng dụng).
    await check_rate(f"react:{user.id}", limit=30, window_seconds=60)
    await community.set_reaction(session, content_id, user.id, payload.type)
    summary = await _summary(session, content_id, user)
    await realtime.publish(
        content_id,
        {"kind": "reaction", "counts": summary.counts, "total": summary.total},
    )
    return summary


@router.delete("/{content_id}/reaction", response_model=ReactionSummary)
async def delete_reaction(
    content_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReactionSummary:
    await _ensure_post(session, content_id)
    await check_rate(f"react:{user.id}", limit=30, window_seconds=60)
    await community.remove_reaction(session, content_id, user.id)
    summary = await _summary(session, content_id, user)
    await realtime.publish(
        content_id,
        {"kind": "reaction", "counts": summary.counts, "total": summary.total},
    )
    return summary


# ---- Lưu bài ----
@router.put("/{content_id}/save")
async def save_post(
    content_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    await _ensure_post(session, content_id)
    await check_rate(f"save:{user.id}", limit=30, window_seconds=60)
    await community.save_post(session, content_id, user.id)
    return {"saved": True}


@router.delete("/{content_id}/save")
async def unsave_post(
    content_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    await check_rate(f"save:{user.id}", limit=30, window_seconds=60)
    await community.unsave_post(session, content_id, user.id)
    return {"saved": False}


# ---- Realtime WebSocket ----
@router.websocket("/{content_id}/ws")
async def community_ws(websocket: WebSocket, content_id: int) -> None:
    """Đẩy bình luận/cảm xúc mới theo thời gian thực cho người đang xem bài.
    Read-only: gửi/đổi tương tác vẫn qua REST (có CSRF + auth)."""
    # Chặn WS cross-site: WebSocket KHÔNG bị ràng buộc CORS nên trang lạ có thể
    # mở kết nối qua trình duyệt nạn nhân. Chỉ chấp nhận Origin trong whitelist;
    # client không phải trình duyệt (test/tool) không gửi Origin -> vẫn cho qua.
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.cors_origins:
        await websocket.close(code=1008)
        return
    # Giới hạn tổng số kết nối WS -> chống cạn kiệt tài nguyên (DoS).
    if not realtime.can_register():
        await websocket.close(code=1013)  # 1013 = try again later
        return
    # Kiểm bài tồn tại trước khi accept
    async with SessionLocal() as session:
        post = await community.get_published_community(session, content_id)
    if post is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    queue = realtime.register(content_id)

    async def _drain_incoming() -> None:
        # Đọc để phát hiện client đóng kết nối; nội dung bỏ qua (WS read-only)
        try:
            while True:
                await websocket.receive_text()
        except Exception:
            pass

    recv = asyncio.create_task(_drain_incoming())
    try:
        while True:
            get_task = asyncio.ensure_future(queue.get())
            done, _ = await asyncio.wait(
                {get_task, recv}, return_when=asyncio.FIRST_COMPLETED
            )
            if recv in done:
                get_task.cancel()
                break
            await websocket.send_text(get_task.result())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        recv.cancel()
        realtime.unregister(content_id, queue)
