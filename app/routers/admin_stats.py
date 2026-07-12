"""Dashboard quản trị: số liệu tổng quan + nhật ký hoạt động. CHỈ admin.

Endpoint read-only, tổng hợp nhanh bằng aggregate SQL — frontend poll định kỳ để
'real-time'. Không tái dùng schema nội bộ nào rò rỉ; số liệu là tổng hợp thuần.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import PaginationParams, require_role
from app.models.activity import ActivityLog
from app.models.community import Comment, PostReaction, SavedPost
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType, UserRole
from app.models.media import Media
from app.models.user import User
from app.schemas.pagination import Page
from app.schemas.stats import ActivityOut, StatsOut
from app.services import realtime

router = APIRouter(prefix="/admin", tags=["dashboard"])

_admin = require_role(UserRole.admin)


def _fill(rows: list[tuple], keys) -> dict[str, int]:
    """Gom (enum, count) thành dict, đảm bảo MỌI key của enum đều có mặt (0 nếu thiếu)
    -> frontend luôn nhận đủ trường, khỏi phải phòng thủ undefined."""
    counts = {str(k): 0 for k in keys}
    for key, num in rows:
        counts[str(getattr(key, "value", key))] = num
    return counts


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_admin),
) -> StatsOut:
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(days=1)

    # ---- Nội dung ----
    status_rows = (
        await session.execute(
            select(Content.status, func.count()).group_by(Content.status)
        )
    ).all()
    type_rows = (
        await session.execute(
            select(Content.type, func.count()).group_by(Content.type)
        )
    ).all()
    by_status = _fill(status_rows, ContentStatus)
    by_type = _fill(type_rows, ContentType)
    content_total = sum(by_status.values())
    published_last_7d = (
        await session.scalar(
            select(func.count())
            .select_from(Content)
            .where(
                Content.status == ContentStatus.published,
                Content.published_at >= week_ago,
            )
        )
    ) or 0

    # ---- Tài khoản ----
    role_rows = (
        await session.execute(select(User.role, func.count()).group_by(User.role))
    ).all()
    by_role = _fill(role_rows, UserRole)
    users_total = sum(by_role.values())
    users_active = (
        await session.scalar(
            select(func.count()).select_from(User).where(User.is_active.is_(True))
        )
    ) or 0

    # ---- Media ----
    media_row = (
        await session.execute(
            select(
                func.count(Media.id),
                func.coalesce(func.sum(Media.size), 0),
                func.count(Media.id).filter(Media.mime_type.like("image/%")),
                func.count(Media.id).filter(Media.mime_type.like("video/%")),
            )
        )
    ).one()

    # ---- Cộng đồng ----
    comments_total = (
        await session.scalar(select(func.count()).select_from(Comment))
    ) or 0
    comments_last_24h = (
        await session.scalar(
            select(func.count())
            .select_from(Comment)
            .where(Comment.created_at >= day_ago)
        )
    ) or 0
    reactions_total = (
        await session.scalar(select(func.count()).select_from(PostReaction))
    ) or 0
    saved_total = (
        await session.scalar(select(func.count()).select_from(SavedPost))
    ) or 0

    return StatsOut(
        content_total=content_total,
        content_by_status=by_status,
        content_by_type=by_type,
        published_last_7d=published_last_7d,
        users_total=users_total,
        users_active=users_active,
        users_pending=users_total - users_active,
        users_by_role=by_role,
        media_count=media_row[0],
        media_size=int(media_row[1]),
        media_images=media_row[2],
        media_videos=media_row[3],
        comments_total=comments_total,
        comments_last_24h=comments_last_24h,
        reactions_total=reactions_total,
        saved_total=saved_total,
        live_connections=realtime.connection_count(),
        generated_at=now,
    )


@router.get("/activity", response_model=Page[ActivityOut])
async def list_activity(
    pagination: PaginationParams = Depends(),
    action: str | None = None,
    actor: str | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_admin),
) -> Page[ActivityOut]:
    # Lọc theo loại thao tác và/hoặc email người thực hiện (khớp một phần)
    filters = []
    if action:
        filters.append(ActivityLog.action == action)
    if actor:
        filters.append(ActivityLog.actor_email.ilike(f"%{actor}%"))

    total = await session.scalar(
        select(func.count()).select_from(ActivityLog).where(*filters)
    )
    rows = await session.scalars(
        select(ActivityLog)
        .where(*filters)
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    return Page.create(
        items=[ActivityOut.from_model(r) for r in rows],
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
    )
