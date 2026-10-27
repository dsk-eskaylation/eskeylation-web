"""Add an optional user-written bio to accounts."""

from alembic import op
import sqlalchemy as sa

revision = "r7b9d1f3a5c6"
down_revision = "q6a8c0e2f4b5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("users", "bio")
