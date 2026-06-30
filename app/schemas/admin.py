"""Schema khu vực quản trị (CMS) — lộ đầy đủ field nội bộ cho biên tập viên."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.content import Content
from app.models.enums import ContentStatus, ContentType
from app.services.storage import get_storage


class ContentMediaIn(BaseModel):
    media_id: int
    caption: str | None = None
    position: int = 0
    is_primary: bool = False


class ContentMediaOut(BaseModel):
    media_id: int
    url: str
    caption: str | None = None
    position: int = 0
    is_primary: bool = False
    mime_type: str
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    alt_text: str | None = None


class ContentCreate(BaseModel):
    type: ContentType
    title: str = Field(min_length=1, max_length=255)
    summary: str | None = None
    body: dict = Field(default_factory=dict)
    media: list[ContentMediaIn] = Field(default_factory=list)


class ContentUpdate(BaseModel):
    """Cập nhật một phần — chỉ field được gửi mới thay đổi."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = None
    body: dict | None = None
    media: list[ContentMediaIn] | None = None


class ContentAdminRead(BaseModel):
    id: int
    type: ContentType
    title: str
    slug: str
    status: ContentStatus
    summary: str | None = None
    body: dict
    author_id: int | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    media: list[ContentMediaOut]

    @classmethod
    def from_model(cls, content: Content) -> "ContentAdminRead":
        storage = get_storage()
        media = [
            ContentMediaOut(
                media_id=link.media_id,
                url=storage.url(link.media.storage_key),
                caption=link.caption,
                position=link.position,
                is_primary=link.is_primary,
                mime_type=link.media.mime_type,
                width=link.media.width,
                height=link.media.height,
                duration=link.media.duration,
                alt_text=link.media.alt_text,
            )
            for link in content.media_links
        ]
        return cls(
            id=content.id,
            type=content.type,
            title=content.title,
            slug=content.slug,
            status=content.status,
            summary=content.summary,
            body=content.body,
            author_id=content.author_id,
            published_at=content.published_at,
            created_at=content.created_at,
            updated_at=content.updated_at,
            media=media,
        )
