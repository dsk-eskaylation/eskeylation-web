"""Music albums: albums table, contents.album_id + track_no."""

from alembic import op
import sqlalchemy as sa

revision = "n3d5f7b9c1e2"
down_revision = "m2c4e6a8b0d1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_table(
        "albums",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("kind", sa.String(16), nullable=False, server_default="album"),
        sa.Column("year", sa.SmallInteger()),
        sa.Column("cover_url", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
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
        sa.CheckConstraint(
            "kind IN ('album', 'mixtape', 'ep', 'collection')", name="ck_albums_kind"
        ),
        sa.CheckConstraint(
            "year IS NULL OR year BETWEEN 1990 AND 2100", name="ck_albums_year"
        ),
        sa.CheckConstraint(
            "cover_url IS NULL OR cover_url LIKE 'https://%'",
            name="ck_albums_cover_https",
        ),
    )
    op.execute("ALTER TABLE public.albums ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY deny_all ON public.albums "
        "AS PERMISSIVE FOR ALL TO public USING (false) WITH CHECK (false)"
    )

    op.add_column(
        "contents",
        sa.Column(
            "album_id",
            sa.Integer(),
            sa.ForeignKey("albums.id", ondelete="SET NULL"),
        ),
    )
    op.add_column("contents", sa.Column("track_no", sa.SmallInteger()))
    op.create_index("ix_contents_album_id", "contents", ["album_id"])
    op.create_index(
        "uq_contents_album_track",
        "contents",
        ["album_id", "track_no"],
        unique=True,
        postgresql_where=sa.text("album_id IS NOT NULL AND track_no IS NOT NULL"),
    )
    op.create_check_constraint(
        "ck_contents_album_music", "contents", "album_id IS NULL OR type = 'music'"
    )
    op.create_check_constraint(
        "ck_contents_track_no", "contents", "track_no IS NULL OR track_no > 0"
    )


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    for name in ("ck_contents_track_no", "ck_contents_album_music"):
        op.drop_constraint(name, "contents", type_="check")
    op.drop_index("uq_contents_album_track", table_name="contents")
    op.drop_index("ix_contents_album_id", table_name="contents")
    op.drop_column("contents", "track_no")
    op.drop_column("contents", "album_id")
    op.drop_table("albums")
