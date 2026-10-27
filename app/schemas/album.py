from pydantic import BaseModel, Field, field_validator

from app.models.enums import AlbumKind
from app.schemas.public import AlbumRef, ContentOut


class AlbumOut(AlbumRef):
    cover_url: str | None = None
    description: str | None = None
    track_count: int = 0


class AlbumDetail(AlbumOut):
    tracks: list[ContentOut] = Field(default_factory=list)


class GenreCount(BaseModel):
    name: str
    count: int


def _https_or_none(value: str | None) -> str | None:
    value = (value or "").strip() or None
    if value and not value.startswith("https://"):
        raise ValueError("Ảnh bìa phải là link HTTPS")
    return value


class AlbumIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    kind: AlbumKind = AlbumKind.album
    year: int | None = Field(default=None, ge=1990, le=2100)
    cover_url: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=5000)
    position: int = Field(default=0, ge=0, le=10_000)

    _cover = field_validator("cover_url")(_https_or_none)


class AlbumUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    kind: AlbumKind | None = None
    year: int | None = Field(default=None, ge=1990, le=2100)
    cover_url: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=5000)
    position: int | None = Field(default=None, ge=0, le=10_000)

    _cover = field_validator("cover_url")(_https_or_none)

    @field_validator("title", "kind", "position")
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError("Không được đặt trường này thành null")
        return value


class AlbumAdminRead(AlbumOut):
    id: int
    position: int
