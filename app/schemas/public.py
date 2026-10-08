from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ContentType


class MediaOut(BaseModel):
    url: str
    caption: str | None = None
    alt_text: str | None = None
    is_primary: bool = False
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    mime_type: str


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
