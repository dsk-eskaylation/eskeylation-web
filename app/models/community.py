"""Tương tác cộng đồng: bình luận, cảm xúc (reaction), lưu bài.

Đều gắn với một Content type=community. Chỉ user đã đăng nhập mới tạo được
(kiểm ở router). Xoá content -> xoá kèm tương tác (ondelete CASCADE).
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ReactionType
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


def _reaction_values() -> str:
    return ", ".join(f"'{r.value}'" for r in ReactionType)


class Comment(TimestampMixin, Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), index=True
    )
    # Xoá user -> giữ bình luận nhưng ẩn danh (hiển thị "Người dùng đã xoá")
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text)

    user: Mapped["User | None"] = relationship(lazy="joined")

    __table_args__ = (
        # Liệt kê bình luận mới nhất theo bài -> index phủ (content_id, created_at)
        Index("ix_comments_content_created", "content_id", "created_at"),
    )


class PostReaction(TimestampMixin, Base):
    __tablename__ = "post_reactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # native_enum=False -> lưu VARCHAR + CHECK ở tầng DB (đồng bộ db-review C4)
    type: Mapped[ReactionType] = mapped_column(
        Enum(ReactionType, native_enum=False, length=20)
    )

    __table_args__ = (
        # Mỗi user chỉ 1 cảm xúc / bài (đổi loại = update)
        UniqueConstraint("content_id", "user_id", name="uq_reaction_user_content"),
        CheckConstraint(f"type IN ({_reaction_values()})", name="ck_reactions_type"),
    )


class SavedPost(TimestampMixin, Base):
    __tablename__ = "saved_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    __table_args__ = (
        UniqueConstraint("content_id", "user_id", name="uq_saved_user_content"),
    )
