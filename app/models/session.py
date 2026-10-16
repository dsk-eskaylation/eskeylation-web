"""Phiên có định danh để logout thu hồi token ngay, độc lập giữa thiết bị."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_user_sessions_expires_at", "expires_at"),)
