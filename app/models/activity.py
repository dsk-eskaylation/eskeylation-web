"""Nhật ký hoạt động CMS (audit log).

Ghi lại MỌI thao tác quản trị (tạo/sửa/publish/gỡ/lưu trữ/xóa/nhân bản nội dung,
tạo/sửa tài khoản) để admin biết chính xác AI đã làm GÌ, KHI NÀO, trên đối tượng
nào. Các trường actor_email / entity_title được LƯU BẢN SAO (denormalize) tại thời
điểm ghi log -> khi user hoặc nội dung bị xóa, dòng log vẫn đọc được đầy đủ.
"""

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class ActivityLog(TimestampMixin, Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Xóa user -> giữ log nhưng bỏ liên kết (đã có actor_email dự phòng).
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_email: Mapped[str | None] = mapped_column(String(255))
    # Hành động: create/update/publish/unpublish/archive/delete/duplicate
    # /user_create/user_update. Lưu VARCHAR (không enum) để thêm loại khỏi migration.
    action: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str] = mapped_column(String(20))  # content / user
    entity_id: Mapped[int | None] = mapped_column()
    # Bản sao tiêu đề/email đối tượng tại thời điểm thao tác (đọc được cả sau khi xóa)
    entity_title: Mapped[str | None] = mapped_column(String(255))
    # Chi tiết bổ sung: field đã đổi, type, status cũ/mới... (tùy hành động)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        # Liệt kê hoạt động mới nhất trước -> index theo created_at
        Index("ix_activity_logs_created", "created_at"),
    )
