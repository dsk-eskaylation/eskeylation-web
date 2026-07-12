"""Đóng góp lời bài hát từ người dùng (chờ admin duyệt).

Không ghi đè trực tiếp body.lyrics — lưu suggestion để kiểm duyệt.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class LyricSuggestion(TimestampMixin, Base):
    __tablename__ = "lyric_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text)
    # pending | accepted | rejected — admin duyệt
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)

    user: Mapped["User | None"] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_lyric_suggestions_content", "content_id", "status"),
    )
