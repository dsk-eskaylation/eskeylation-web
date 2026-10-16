"""Định danh cho tương tác; không lưu bản sao nội dung hoặc file Drive."""

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class InteractionTarget(Base):
    __tablename__ = "interaction_targets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    content_id: Mapped[int | None] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), unique=True
    )
    drive_file_id: Mapped[str | None] = mapped_column(String(200), unique=True)

    __table_args__ = (
        CheckConstraint(
            "(id > 0 AND content_id IS NOT NULL AND content_id = id "
            "AND drive_file_id IS NULL) OR "
            "(id < 0 AND content_id IS NULL AND drive_file_id IS NOT NULL)",
            name="ck_interaction_targets_source",
        ),
    )
