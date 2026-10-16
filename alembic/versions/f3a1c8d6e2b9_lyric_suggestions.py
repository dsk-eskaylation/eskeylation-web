"""Bảng đóng góp lời bài hát (lyric_suggestions).

Revision ID: f3a1c8d6e2b9
Revises: e2f7a9c4b1d8
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a1c8d6e2b9"
down_revision: Union[str, Sequence[str], None] = "e2f7a9c4b1d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lyric_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "content_id",
            sa.Integer(),
            sa.ForeignKey("contents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="pending", nullable=False
        ),
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
        "ix_lyric_suggestions_content_id", "lyric_suggestions", ["content_id"]
    )
    op.create_index(
        "ix_lyric_suggestions_status", "lyric_suggestions", ["status"]
    )
    op.create_index(
        "ix_lyric_suggestions_content", "lyric_suggestions", ["content_id", "status"]
    )
    op.execute("ALTER TABLE public.lyric_suggestions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("lyric_suggestions")
