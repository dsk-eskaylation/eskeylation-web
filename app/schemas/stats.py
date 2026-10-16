"""Schema cho Dashboard quản trị: số liệu tổng quan + nhật ký hoạt động."""

from datetime import datetime

from pydantic import BaseModel

from app.models.activity import ActivityLog


class StatsOut(BaseModel):
    # Nội dung
    content_total: int
    content_by_status: dict[str, int]
    content_by_type: dict[str, int]
    published_last_7d: int
    # Tài khoản
    users_total: int
    users_active: int
    users_pending: int
    users_by_role: dict[str, int]
    # Media
    media_count: int
    media_size: int  # tổng byte
    media_images: int
    media_videos: int
    # Cộng đồng
    comments_total: int
    comments_last_24h: int
    reactions_total: int
    saved_total: int
    # Trực tiếp (số kết nối WebSocket đang mở trong tiến trình này)
    live_connections: int
    generated_at: datetime


class ActivityOut(BaseModel):
    id: int
    actor_email: str | None = None
    action: str
    entity_type: str
    entity_id: int | None = None
    entity_title: str | None = None
    detail: dict
    created_at: datetime

    @classmethod
    def from_model(cls, log: ActivityLog) -> "ActivityOut":
        return cls(
            id=log.id,
            actor_email=log.actor_email,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            entity_title=log.entity_title,
            detail=log.detail or {},
            created_at=log.created_at,
        )
