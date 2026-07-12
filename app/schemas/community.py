from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ReactionType


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class ReactionIn(BaseModel):
    type: ReactionType


class ReactionSummary(BaseModel):
    """Đếm cảm xúc theo loại + tổng + cảm xúc của user hiện tại (nếu có)."""

    counts: dict[str, int] = {}
    total: int = 0
    my_reaction: ReactionType | None = None


class CommentOut(BaseModel):
    id: int
    content_id: int
    body: str
    author_name: str
    created_at: datetime
    updated_at: datetime
    # edited = đã chỉnh sửa (updated_at > created_at) -> UI hiện thời gian sửa + nhãn
    edited: bool = False
    # Cảm xúc trên bình luận + cờ cho biết đây có phải bình luận của user hiện tại
    # (để UI hiện nút Sửa/Xoá).
    reactions: ReactionSummary = ReactionSummary()
    is_mine: bool = False


class InteractionOut(BaseModel):
    """Tổng quan tương tác 1 bài — dùng để hydrate UI khi tải feed."""

    content_id: int
    reactions: ReactionSummary
    comment_count: int
    saved: bool = False
