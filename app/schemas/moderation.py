"""Schema kiểm duyệt: từ cấm."""

from datetime import datetime

from pydantic import BaseModel, Field


class BannedWordIn(BaseModel):
    word: str = Field(min_length=1, max_length=100)


class BannedWordOut(BaseModel):
    id: int
    word: str
    created_at: datetime
