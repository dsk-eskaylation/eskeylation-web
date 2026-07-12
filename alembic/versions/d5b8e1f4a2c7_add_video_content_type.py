"""Thêm loại nội dung 'video' vào CHECK constraint ck_contents_type.

Cột contents.type là VARCHAR (native_enum=False) nên DB không tự biết enum;
CHECK constraint là nơi chốt danh sách giá trị hợp lệ. Trang /video mới cần
loại 'video' đứng riêng với 'music'/'gallery'/'community'/'homepage'.

Audio của music lưu trong body JSONB (body.audio_url) -> không cần đổi schema.

Revision ID: d5b8e1f4a2c7
Revises: c7e21a5f9d03
Create Date: 2026-07-08
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d5b8e1f4a2c7"
down_revision: Union[str, Sequence[str], None] = "c7e21a5f9d03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_contents_type", "contents", type_="check")
    op.create_check_constraint(
        "ck_contents_type",
        "contents",
        "type IN ('music', 'gallery', 'community', 'homepage', 'video')",
    )


def downgrade() -> None:
    # Không còn hàng 'video' mới được phép -> trả về danh sách cũ
    op.drop_constraint("ck_contents_type", "contents", type_="check")
    op.create_check_constraint(
        "ck_contents_type",
        "contents",
        "type IN ('music', 'gallery', 'community', 'homepage')",
    )
