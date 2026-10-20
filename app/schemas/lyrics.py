"""Admin-only lyric review payloads; public submissions use the music router."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

LyricStatus = Literal["pending", "accepted", "rejected"]


class LyricReview(BaseModel):
    status: Literal["accepted", "rejected"]


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
