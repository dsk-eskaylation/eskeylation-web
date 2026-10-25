"""Schema khu vực quản trị (CMS) — lộ đầy đủ field nội bộ cho biên tập viên."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.content import Content
from app.models.enums import ContentStatus, ContentType, MusicProvider
from app.schemas.content_body import validate_body_budget
from app.services.sanitize import player_url, restore_plain_values
from app.services.storage import get_storage


class ContentMediaIn(BaseModel):
    media_id: int
    caption: str | None = Field(default=None, max_length=2000)
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
    summary: str | None = Field(default=None, max_length=20_000)
    body: dict = Field(default_factory=dict)
    media: list[ContentMediaIn] = Field(default_factory=list, max_length=500)
    source_url: str | None = Field(default=None, max_length=1000)
    cover_url: str | None = Field(default=None, max_length=1000)

    @field_validator("body")
    @classmethod
    def bounded_body(cls, value: dict) -> dict:
        return validate_body_budget(value)


class ContentUpdate(BaseModel):
    """Cập nhật một phần — chỉ field được gửi mới thay đổi."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=20_000)
    body: dict | None = None
    media: list[ContentMediaIn] | None = Field(default=None, max_length=500)
    # Explicit null clears; omitted keeps the stored value.
    source_url: str | None = Field(default=None, max_length=1000)
    cover_url: str | None = Field(default=None, max_length=1000)
    expected_updated_at: datetime | None = None

    @field_validator("title", "body")
    @classmethod
    def reject_explicit_null(cls, value: str | dict | None) -> str | dict:
        # Omission leaves the stored value unchanged; explicit null is not a delete.
        if value is None:
            raise ValueError("Không được đặt tiêu đề hoặc nội dung thành null")
        return value

    @field_validator("body")
    @classmethod
    def bounded_body(cls, value: dict | None) -> dict | None:
        return validate_body_budget(value) if value is not None else value


class ContentAdminRead(BaseModel):
    id: int
    type: ContentType
    title: str
    slug: str
    status: ContentStatus
    summary: str | None = None
    body: dict
    author_id: int | None = None
    # Email tác giả (nạp riêng ở list) — để CMS hiển thị AI tạo nội dung này
    author_email: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    media: list[ContentMediaOut]
    source_url: str | None = None
    source_provider: MusicProvider | None = None
    player_url: str | None = None
    cover_url: str | None = None

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
            body=restore_plain_values(content.body),
            author_id=content.author_id,
            published_at=content.published_at,
            created_at=content.created_at,
            updated_at=content.updated_at,
            media=media,
            source_url=content.source_url,
            source_provider=content.source_provider,
            player_url=player_url(content.source_url),
            cover_url=content.cover_url,
        )
