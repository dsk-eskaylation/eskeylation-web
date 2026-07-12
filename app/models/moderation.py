"""Kiểm duyệt: danh sách TỪ CẤM do admin quản lý.

Áp dụng khi tạo/sửa nội dung (mô tả + body) và khi gửi bình luận: nếu văn bản
chứa từ trong danh sách -> CHẶN (422). Từ lưu ở dạng chữ thường để so khớp
không phân biệt hoa/thường.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class BannedWord(TimestampMixin, Base):
    __tablename__ = "banned_words"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Lưu chữ thường, unique -> không trùng lặp; so khớp bằng chữ thường.
    word: Mapped[str] = mapped_column(String(100), unique=True, index=True)
