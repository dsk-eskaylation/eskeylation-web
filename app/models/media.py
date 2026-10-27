from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.content import Content


class Media(TimestampMixin, Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    mime_type: Mapped[str] = mapped_column(String(127))
    size: Mapped[int] = mapped_column()
    width: Mapped[int | None] = mapped_column()
    height: Mapped[int | None] = mapped_column()
    duration: Mapped[float | None] = mapped_column()  # giây, cho video
    alt_text: Mapped[str | None] = mapped_column(Text)
    # Thành viên chỉ được gắn ảnh do chính mình tải lên vào bài cộng đồng.
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    variants: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    processing_status: Mapped[str] = mapped_column(
        String(16), default="skipped", server_default="skipped"
    )
    processing_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    processing_next_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    processing_token: Mapped[str | None] = mapped_column(String(36))
    processing_error_code: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (
        CheckConstraint(
            "processing_status IN "
            "('skipped','pending','queued','processing','ready','failed')",
            name="ck_media_processing_status",
        ),
        CheckConstraint(
            "processing_attempts >= 0", name="ck_media_processing_attempts"
        ),
        CheckConstraint(
            "jsonb_typeof(variants) = 'object'", name="ck_media_variants_object"
        ),
        Index(
            "ix_media_processing_queue",
            "processing_status",
            "processing_next_at",
            "processing_lease_until",
            postgresql_where=text(
                "processing_status IN ('pending','queued','processing')"
            ),
        ),
    )


class ContentMedia(Base):
    """Bảng nối Content <-> Media (M-N CÓ thuộc tính)."""

    __tablename__ = "content_media"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), index=True
    )
    media_id: Mapped[int] = mapped_column(
        ForeignKey("media.id", ondelete="CASCADE"), index=True
    )
    caption: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(default=0)
    is_primary: Mapped[bool] = mapped_column(default=False)

    content: Mapped["Content"] = relationship(back_populates="media_links")
    media: Mapped["Media"] = relationship()

    __table_args__ = (
        # Một media chỉ gắn 1 lần vào 1 content (db-review C2)
        UniqueConstraint(
            "content_id", "media_id", name="uq_content_media_content_media"
        ),
        # Position không trùng trong 1 content; DEFERRABLE để reorder swap
        # trong 1 transaction không vấp constraint giữa chừng (db-review M2)
        UniqueConstraint(
            "content_id",
            "position",
            name="uq_content_media_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        # Tối đa 1 primary mỗi content (db-review C1)
        Index(
            "uq_content_media_one_primary",
            "content_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )
