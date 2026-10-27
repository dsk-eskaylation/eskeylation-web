"""Thông báo cho người dùng khi có người tương tác với bài / bình luận của họ."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin

KINDS = ("post_reaction", "post_comment", "comment_reaction")


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(30))
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("interaction_targets.id", ondelete="CASCADE")
    )
    comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        CheckConstraint(
            "kind IN ('post_reaction', 'post_comment', 'comment_reaction')",
            name="ck_notifications_kind",
        ),
    )
