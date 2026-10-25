from datetime import datetime

from pydantic import BaseModel, PrivateAttr

from app.models.enums import AlbumKind, ContentType, MusicProvider


class MediaOut(BaseModel):
    media_id: int | None = None
    url: str
    preview_url: str | None = None
    stream_url: str | None = None
    original_url: str | None = None
    srcset: str | None = None
    caption: str | None = None
    alt_text: str | None = None
    is_primary: bool = False
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    mime_type: str


class AlbumRef(BaseModel):
    slug: str
    title: str
    kind: AlbumKind
    year: int | None = None


class ContentOut(BaseModel):
    """Schema công khai — KHÔNG lộ status, author_id hay field nội bộ."""

    id: int
    type: ContentType
    title: str
    slug: str
    summary: str | None = None
    body: dict
    published_at: datetime | None = None
    media: list[MediaOut] = []
    source_url: str | None = None
    source_provider: MusicProvider | None = None
    player_url: str | None = None
    cover_url: str | None = None
    album: AlbumRef | None = None
    track_no: int | None = None
    # Chỉ tồn tại trong bộ nhớ backend, không nằm trong schema/JSON public.
    _drive: dict = PrivateAttr(default_factory=dict)
