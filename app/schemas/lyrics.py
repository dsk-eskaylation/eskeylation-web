"""Admin-only lyric review payloads; public submissions use the music router."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

LyricStatus = Literal["pending", "accepted", "rejected"]


class LyricReview(BaseModel):
    status: Literal["accepted", "rejected"]
    # Admin có thể sửa lời (ví dụ từ nhạy cảm) trước khi duyệt; credit vẫn là người gửi.
    body: str | None = Field(default=None, min_length=1, max_length=8000)


class LyricSuggestionOut(BaseModel):
    id: int
    content_id: int
    cms_content_id: int | None
    title: str | None
    user_email: str | None
    body: str
    status: LyricStatus
    created_at: datetime
    can_accept: bool
