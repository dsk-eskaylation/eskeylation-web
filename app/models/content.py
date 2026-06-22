from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ContentStatus, ContentType
from app.models.mixins import TimestampMixin


class Content(TimestampMixin, Base):
    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, native_enum=False, length=20), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
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
    published_at: Mapped[datetime | None] = mapped_column()

    media_links: Mapped[list["ContentMedia"]] = relationship(
        back_populates="content",
        cascade="all, delete-orphan",
        order_by="ContentMedia.position",
    )
