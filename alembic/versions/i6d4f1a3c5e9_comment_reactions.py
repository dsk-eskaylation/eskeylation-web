"""Cảm xúc trên bình luận (comment_reactions).

Cho phép thả cảm xúc (6 loại) lên từng bình luận, tương tự post_reactions.
Bật RLS như các bảng public khác (backend dùng role owner nên bypass).

Revision ID: i6d4f1a3c5e9
Revises: h5c3e0f2b4d8
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "i6d4f1a3c5e9"
down_revision: Union[str, Sequence[str], None] = "h5c3e0f2b4d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TYPES = "'like', 'love', 'haha', 'wow', 'sad', 'angry'"


def upgrade() -> None:
    op.create_table(
        "comment_reactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "comment_id",
            sa.Integer(),
            sa.ForeignKey("comments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=20), nullable=False),
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
        sa.UniqueConstraint(
            "comment_id", "user_id", name="uq_comment_reaction_user_comment"
        ),
        sa.CheckConstraint(f"type IN ({_TYPES})", name="ck_comment_reactions_type"),
    )
    op.create_index(
        "ix_comment_reactions_comment_id", "comment_reactions", ["comment_id"]
    )
    op.create_index("ix_comment_reactions_user_id", "comment_reactions", ["user_id"])
    op.execute("ALTER TABLE public.comment_reactions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_comment_reactions_user_id", table_name="comment_reactions")
    op.drop_index("ix_comment_reactions_comment_id", table_name="comment_reactions")
    op.drop_table("comment_reactions")
