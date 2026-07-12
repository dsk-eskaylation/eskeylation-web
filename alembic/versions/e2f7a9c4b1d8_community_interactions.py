"""Tương tác cộng đồng: comments, post_reactions, saved_posts.

Bật RLS như các bảng public khác (Supabase expose PostgREST) — backend dùng
role owner nên bypass, chặn truy cập anon/authenticated qua Data API.

Revision ID: e2f7a9c4b1d8
Revises: d5b8e1f4a2c7
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2f7a9c4b1d8"
down_revision: Union[str, Sequence[str], None] = "d5b8e1f4a2c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("comments", "post_reactions", "saved_posts")


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
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


def upgrade() -> None:
    op.create_table(
        "comments",
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
        *_timestamps(),
    )
    op.create_index("ix_comments_content_id", "comments", ["content_id"])
    op.create_index(
        "ix_comments_content_created", "comments", ["content_id", "created_at"]
    )

    op.create_table(
        "post_reactions",
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
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=20), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "content_id", "user_id", name="uq_reaction_user_content"
        ),
        sa.CheckConstraint(
            "type IN ('like', 'love', 'haha', 'wow', 'sad', 'angry')",
            name="ck_reactions_type",
        ),
    )
    op.create_index("ix_post_reactions_content_id", "post_reactions", ["content_id"])
    op.create_index("ix_post_reactions_user_id", "post_reactions", ["user_id"])

    op.create_table(
        "saved_posts",
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
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *_timestamps(),
        sa.UniqueConstraint("content_id", "user_id", name="uq_saved_user_content"),
    )
    op.create_index("ix_saved_posts_content_id", "saved_posts", ["content_id"])
    op.create_index("ix_saved_posts_user_id", "saved_posts", ["user_id"])

    for table in _NEW_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("saved_posts")
    op.drop_table("post_reactions")
    op.drop_table("comments")
