"""Music added by SoundCloud/YouTube/Vimeo link: source + cover columns on contents."""

from alembic import op
import sqlalchemy as sa

revision = "m2c4e6a8b0d1"
down_revision = "f42a19c72e10"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    # Nullable, không default -> Postgres chỉ sửa catalog, không rewrite bảng.
    op.add_column("contents", sa.Column("source_url", sa.Text()))
    op.add_column("contents", sa.Column("source_provider", sa.String(16)))
    op.add_column("contents", sa.Column("cover_url", sa.Text()))
    op.create_check_constraint(
        "ck_contents_source_provider",
        "contents",
        "source_provider IN ('soundcloud', 'youtube', 'vimeo')",
    )
    op.create_check_constraint(
        "ck_contents_source_pair",
        "contents",
        "(source_url IS NULL) = (source_provider IS NULL)",
    )
    op.create_check_constraint(
        "ck_contents_cover_https",
        "contents",
        "cover_url IS NULL OR cover_url LIKE 'https://%'",
    )


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    for name in (
        "ck_contents_cover_https",
        "ck_contents_source_pair",
        "ck_contents_source_provider",
    ):
        op.drop_constraint(name, "contents", type_="check")
    for name in ("cover_url", "source_provider", "source_url"):
        op.drop_column("contents", name)
