"""Record which account uploaded a media file, so members can attach only their own."""

from alembic import op
import sqlalchemy as sa

revision = "t9d1f3b5c7e8"
down_revision = "s8c0e2a4b6d7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "media",
        sa.Column(
            "uploaded_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_media_uploaded_by", "media", ["uploaded_by"])


def downgrade():
    op.drop_index("ix_media_uploaded_by", table_name="media")
    op.drop_column("media", "uploaded_by")
