"""DB hardening: constraint toàn vẹn + index hiệu năng (docs/db-review.md).

- C1: tối đa 1 primary/content (unique partial index)
- C2: UNIQUE(content_id, media_id)
- M2: UNIQUE(content_id, position) DEFERRABLE
- C4: CHECK enum type/status/role (native_enum=False lưu VARCHAR)
- M1: CHECK published => published_at NOT NULL
- C3: partial index (type, published_at DESC, id DESC) WHERE published
- M5: index author_id
- M3: slug unique theo type thay vì toàn cục

Revision ID: a1c9f3d27b64
Revises: 3e6a7a439b15
Create Date: 2026-07-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1c9f3d27b64"
down_revision: Union[str, Sequence[str], None] = "3e6a7a439b15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- Dọn dữ liệu cũ trước khi siết constraint (idempotent) ----
    # Nhiều primary trên 1 content: giữ bản ghi id nhỏ nhất
    op.execute(
        """
        UPDATE content_media SET is_primary = false WHERE id IN (
            SELECT id FROM (
                SELECT id, row_number() OVER (
                    PARTITION BY content_id ORDER BY id
                ) AS rn
                FROM content_media WHERE is_primary
            ) t WHERE t.rn > 1
        )
        """
    )
    # Position trùng trong 1 content: đánh số lại 0..n-1 giữ thứ tự cũ
    op.execute(
        """
        UPDATE content_media cm SET position = r.rn FROM (
            SELECT id, row_number() OVER (
                PARTITION BY content_id ORDER BY position, id
            ) - 1 AS rn
            FROM content_media
        ) r WHERE cm.id = r.id AND cm.position <> r.rn
        """
    )

    # ---- content_media: toàn vẹn quan hệ ----
    op.create_unique_constraint(
        "uq_content_media_content_media", "content_media", ["content_id", "media_id"]
    )
    op.create_unique_constraint(
        "uq_content_media_position",
        "content_media",
        ["content_id", "position"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_index(
        "uq_content_media_one_primary",
        "content_media",
        ["content_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )

    # ---- CHECK enum (DB không tự biết vì cột là VARCHAR) ----
    op.create_check_constraint(
        "ck_contents_type",
        "contents",
        "type IN ('music', 'gallery', 'community', 'homepage')",
    )
    op.create_check_constraint(
        "ck_contents_status",
        "contents",
        "status IN ('draft', 'published', 'archived')",
    )
    op.create_check_constraint(
        "ck_contents_published_at",
        "contents",
        "status <> 'published' OR published_at IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_users_role", "users", "role IN ('admin', 'editor', 'author')"
    )

    # ---- Index hiệu năng ----
    op.create_index("ix_contents_author_id", "contents", ["author_id"])
    op.create_index(
        "ix_contents_public_list",
        "contents",
        ["type", sa.text("published_at DESC"), sa.text("id DESC")],
        postgresql_where=sa.text("status = 'published'"),
    )

    # ---- Slug: unique toàn cục -> unique theo (type, slug) ----
    op.drop_index(op.f("ix_contents_slug"), table_name="contents")
    op.create_index(op.f("ix_contents_slug"), "contents", ["slug"], unique=False)
    op.create_unique_constraint("uq_contents_type_slug", "contents", ["type", "slug"])


def downgrade() -> None:
    op.drop_constraint("uq_contents_type_slug", "contents", type_="unique")
    op.drop_index(op.f("ix_contents_slug"), table_name="contents")
    op.create_index(op.f("ix_contents_slug"), "contents", ["slug"], unique=True)

    op.drop_index("ix_contents_public_list", table_name="contents")
    op.drop_index("ix_contents_author_id", table_name="contents")

    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_constraint("ck_contents_published_at", "contents", type_="check")
    op.drop_constraint("ck_contents_status", "contents", type_="check")
    op.drop_constraint("ck_contents_type", "contents", type_="check")

    op.drop_index("uq_content_media_one_primary", table_name="content_media")
    op.drop_constraint("uq_content_media_position", "content_media", type_="unique")
    op.drop_constraint(
        "uq_content_media_content_media", "content_media", type_="unique"
    )
