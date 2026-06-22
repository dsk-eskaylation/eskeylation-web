from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
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
