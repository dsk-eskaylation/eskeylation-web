"""Ghi nhật ký hoạt động CMS (audit log).

Best-effort: log là phụ trợ, KHÔNG được làm hỏng thao tác chính. Vì vậy log()
tự bắt lỗi + rollback riêng nếu ghi thất bại (thao tác chính đã commit trước đó
ở router). Mỗi log là một commit riêng, độc lập với transaction nghiệp vụ.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityLog
from app.models.user import User

logger = logging.getLogger(__name__)

# Hằng hành động — dùng thống nhất để frontend map nhãn tiếng Việt.
CREATE = "create"
UPDATE = "update"
PUBLISH = "publish"
UNPUBLISH = "unpublish"
ARCHIVE = "archive"
DELETE = "delete"
DUPLICATE = "duplicate"
USER_CREATE = "user_create"
USER_UPDATE = "user_update"
BANNED_ADD = "banned_add"
BANNED_REMOVE = "banned_remove"
COMMENT_DELETE = "comment_delete"


async def log(
    session: AsyncSession,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    entity_title: str | None = None,
    detail: dict | None = None,
) -> None:
    """Ghi một dòng nhật ký. Không bao giờ ném lỗi ra ngoài."""
    entry = ActivityLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_title=entity_title,
        detail=detail or {},
    )
    try:
        session.add(entry)
        await session.commit()
    except Exception:
        logger.warning("Ghi activity log thất bại (%s %s)", action, entity_type)
        await session.rollback()
