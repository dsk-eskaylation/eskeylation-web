"""Expire only new unattached community uploads; preserve existing media."""

import sqlalchemy as sa
from alembic import op

revision = "u0e2f4a6b8c9"
down_revision = "t9d1f3b5c7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "media",
        sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "media",
        sa.Column(
            "cleanup_pending", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(
        "ix_media_upload_expiry",
        "media",
        ["upload_expires_at"],
        postgresql_where=sa.text("upload_expires_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_media_upload_expiry", table_name="media")
    op.drop_column("media", "cleanup_pending")
    op.drop_column("media", "upload_expires_at")
