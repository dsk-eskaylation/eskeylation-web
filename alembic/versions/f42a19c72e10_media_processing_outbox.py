"""Durable media processing state; existing files remain unchanged."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f42a19c72e10"
down_revision = "d0195e70ffd3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column(
        "media",
        sa.Column(
            "variants",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "media",
        sa.Column(
            "processing_status", sa.String(16), server_default="skipped", nullable=False
        ),
    )
    op.add_column(
        "media",
        sa.Column(
            "processing_attempts", sa.Integer(), server_default="0", nullable=False
        ),
    )
    for name in ("processing_next_at", "processing_lease_until"):
        op.add_column("media", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column("media", sa.Column("processing_token", sa.String(36)))
    op.add_column("media", sa.Column("processing_error_code", sa.String(32)))
    op.create_check_constraint(
        "ck_media_processing_status",
        "media",
        "processing_status IN ('skipped','pending','queued','processing','ready','failed')",
    )
    op.create_check_constraint(
        "ck_media_processing_attempts", "media", "processing_attempts >= 0"
    )
    op.create_check_constraint(
        "ck_media_variants_object", "media", "jsonb_typeof(variants) = 'object'"
    )
    op.create_index(
        "ix_media_processing_queue",
        "media",
        ["processing_status", "processing_next_at", "processing_lease_until"],
        postgresql_where=sa.text(
            "processing_status IN ('pending','queued','processing')"
        ),
    )


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_index("ix_media_processing_queue", table_name="media")
    for name in (
        "ck_media_processing_status",
        "ck_media_processing_attempts",
        "ck_media_variants_object",
    ):
        op.drop_constraint(name, "media", type_="check")
    for name in (
        "variants",
        "processing_status",
        "processing_attempts",
        "processing_next_at",
        "processing_lease_until",
        "processing_token",
        "processing_error_code",
    ):
        op.drop_column("media", name)
