from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.services.storage import get_storage


class MediaRead(BaseModel):
    """Thông tin một media cho khu vực quản trị."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    mime_type: str
    size: int
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    alt_text: str | None = None
    created_at: datetime
    processing_status: str = "skipped"
    processing_attempts: int = 0
    processing_error_code: str | None = None

    @classmethod
    def from_model(cls, media) -> "MediaRead":
        return cls(
            id=media.id,
            url=get_storage().url(media.storage_key),
            mime_type=media.mime_type,
            size=media.size,
            width=media.width,
            height=media.height,
            duration=media.duration,
            alt_text=media.alt_text,
            created_at=media.created_at,
            processing_status=media.processing_status,
            processing_attempts=media.processing_attempts,
            processing_error_code=media.processing_error_code,
        )
