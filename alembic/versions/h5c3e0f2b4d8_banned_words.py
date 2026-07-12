"""Kiểm duyệt: bảng từ cấm (banned_words).

Admin quản lý danh sách từ ngữ không phù hợp; áp dụng chặn khi tạo/sửa nội dung
(mô tả + body) và khi gửi bình luận. Bật RLS như các bảng public khác (backend
dùng role owner nên bypass).

Revision ID: h5c3e0f2b4d8
Revises: g4b2d9e1a3c7
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "h5c3e0f2b4d8"
down_revision: Union[str, Sequence[str], None] = "g4b2d9e1a3c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "banned_words",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("word", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_banned_words_word", "banned_words", ["word"], unique=True
    )
    op.execute("ALTER TABLE public.banned_words ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_banned_words_word", table_name="banned_words")
    op.drop_table("banned_words")
