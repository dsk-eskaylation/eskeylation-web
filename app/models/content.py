from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ContentStatus, ContentType
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.media import ContentMedia


def _values(enum_cls) -> str:
    """'a','b','c' — cho CHECK constraint bám sát enum Python."""
    return ", ".join(f"'{v.value}'" for v in enum_cls)


class Content(TimestampMixin, Base):
    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, native_enum=False, length=20), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    # Slug unique THEO TYPE (db-review M3) — route public đã tách theo type
    slug: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus, native_enum=False, length=20),
        default=ContentStatus.draft,
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(Text)
    # Dữ liệu riêng theo từng loại nội dung (music/gallery/community/homepage).
    body: Mapped[dict] = mapped_column(JSONB, default=dict)

    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # tsvector cho full-text search (unaccent). Do trigger cập nhật, xem migration.
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    media_links: Mapped[list["ContentMedia"]] = relationship(
        back_populates="content",
        cascade="all, delete-orphan",
        order_by="ContentMedia.position",
    )

    __table_args__ = (
        Index("ix_contents_search_vector", "search_vector", postgresql_using="gin"),
        UniqueConstraint("type", "slug", name="uq_contents_type_slug"),
        # CHECK enum ở tầng DB vì native_enum=False lưu VARCHAR (db-review C4)
        CheckConstraint(
            f"type IN ({_values(ContentType)})", name="ck_contents_type"
        ),
        CheckConstraint(
            f"status IN ({_values(ContentStatus)})", name="ck_contents_status"
        ),
        # published bắt buộc có published_at (db-review M1)
        CheckConstraint(
            "status <> 'published' OR published_at IS NOT NULL",
            name="ck_contents_published_at",
        ),
        Index("ix_contents_author_id", "author_id"),
        # Index phủ query public nóng: type + sort published_at DESC, id DESC
        # chỉ trên hàng published (db-review C3)
        Index(
            "ix_contents_public_list",
            "type",
            text("published_at DESC"),
            text("id DESC"),
            postgresql_where=text("status = 'published'"),
        ),
    )
