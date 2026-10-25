from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import AlbumKind
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.content import Content


class Album(TimestampMixin, Base):
    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True)
    kind: Mapped[AlbumKind] = mapped_column(
        Enum(AlbumKind, native_enum=False, length=16), default=AlbumKind.album
    )
    year: Mapped[int | None] = mapped_column(SmallInteger)
    cover_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # ON DELETE SET NULL unlinks tracks; loading them here would lazy-load in async.
    tracks: Mapped[list["Content"]] = relationship(
        back_populates="album", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('album', 'mixtape', 'ep', 'collection')", name="ck_albums_kind"
        ),
        CheckConstraint(
            "year IS NULL OR year BETWEEN 1990 AND 2100", name="ck_albums_year"
        ),
        CheckConstraint(
            "cover_url IS NULL OR cover_url LIKE 'https://%'",
            name="ck_albums_cover_https",
        ),
    )
