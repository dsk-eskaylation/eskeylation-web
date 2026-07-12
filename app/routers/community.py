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
from app.dependencies import PaginationParams, get_current_user, get_current_user_optional
from app.models.user import User
from app.schemas.community import (
    CommentIn,
    CommentOut,
    InteractionOut,
    ReactionIn,
    ReactionSummary,
)
from app.schemas.pagination import Page
from app.services import community, realtime
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


def _comment_out(c) -> CommentOut:
    return CommentOut(
        id=c.id,
        content_id=c.content_id,
        body=c.body,
        author_name=community.author_name(c.user),
        created_at=c.created_at,
    )


async def _summary(
    session: AsyncSession, content_id: int, user: User | None
) -> ReactionSummary:
    counts = await community.reaction_counts(session, content_id)
    mine = (
        await community.my_reaction(session, content_id, user.id) if user else None
    )
    return ReactionSummary(
        counts=counts, total=sum(counts.values()), my_reaction=mine
    )


# ---- Tổng quan ----
@router.get("/{content_id}/interactions", response_model=InteractionOut)
async def get_interactions(
    content_id: int,
    user: User | None = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_session),
) -> InteractionOut:
    await _ensure_post(session, content_id)
    return InteractionOut(
        content_id=content_id,
        reactions=await _summary(session, content_id, user),
        comment_count=await community.comment_count(session, content_id),
        saved=(
            await community.is_saved(session, content_id, user.id) if user else False
        ),
    )


# ---- Bình luận ----
@router.get("/{content_id}/comments", response_model=Page[CommentOut])
async def list_comments(
    content_id: int,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Page[CommentOut]:
    await _ensure_post(session, content_id)
    items, total = await community.list_comments(
        session, content_id, page=pagination.page, page_size=pagination.page_size
    )
    return Page.create(
        items=[_comment_out(c) for c in items],
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
    comment = await community.create_comment(session, content_id, user, body)
    out = _comment_out(comment)
    await realtime.publish(
        content_id, {"kind": "comment", "comment": out.model_dump(mode="json")}
    )
    return out


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
