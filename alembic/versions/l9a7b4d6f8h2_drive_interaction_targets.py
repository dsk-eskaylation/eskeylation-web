"""Liên kết tương tác với file Drive, giữ nguyên nội dung và tương tác CMS.

Revision ID: l9a7b4d6f8h2
Revises: k8f6h3c5e7g1
"""

import sqlalchemy as sa
from alembic import op

revision = "l9a7b4d6f8h2"
down_revision = "k8f6h3c5e7g1"
branch_labels = None
depends_on = None

_TABLES = ("comments", "post_reactions", "saved_posts", "lyric_suggestions")


def upgrade() -> None:
    op.create_table(
        "interaction_targets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column(
            "content_id",
            sa.Integer(),
            sa.ForeignKey("contents.id", ondelete="CASCADE"),
            unique=True,
        ),
        sa.Column("drive_file_id", sa.String(200), unique=True),
        sa.CheckConstraint(
            "(id > 0 AND content_id IS NOT NULL AND content_id = id "
            "AND drive_file_id IS NULL) OR "
            "(id < 0 AND content_id IS NULL AND drive_file_id IS NOT NULL)",
            name="ck_interaction_targets_source",
        ),
    )
    op.execute(
        "INSERT INTO public.interaction_targets (id, content_id) "
        "SELECT id, id FROM public.contents"
    )
    op.execute(
        "CREATE FUNCTION public.contents_interaction_target_insert() RETURNS trigger "
        "LANGUAGE plpgsql SET search_path = pg_catalog AS $$ BEGIN "
        "INSERT INTO public.interaction_targets (id, content_id) VALUES (NEW.id, NEW.id); "
        "RETURN NEW; END $$"
    )
    op.execute(
        "CREATE TRIGGER contents_interaction_target_insert AFTER INSERT ON public.contents "
        "FOR EACH ROW EXECUTE FUNCTION public.contents_interaction_target_insert()"
    )
    for table in _TABLES:
        op.drop_constraint(f"{table}_content_id_fkey", table, type_="foreignkey")
        op.alter_column(
            table, "content_id", existing_type=sa.Integer(), type_=sa.BigInteger()
        )
        op.create_foreign_key(
            f"{table}_content_id_fkey",
            table,
            "interaction_targets",
            ["content_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.execute("ALTER TABLE public.interaction_targets ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY deny_all ON public.interaction_targets "
        "AS PERMISSIVE FOR ALL TO public USING (false) WITH CHECK (false)"
    )


def downgrade() -> None:
    # Không âm thầm xoá tương tác Drive khi quay về schema cũ.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM public.interaction_targets WHERE id < 0) "
        "THEN RAISE EXCEPTION 'Export Drive interactions before downgrade'; "
        "END IF; END $$"
    )
    for table in _TABLES:
        op.drop_constraint(f"{table}_content_id_fkey", table, type_="foreignkey")
        op.alter_column(
            table, "content_id", existing_type=sa.BigInteger(), type_=sa.Integer()
        )
        op.create_foreign_key(
            f"{table}_content_id_fkey",
            table,
            "contents",
            ["content_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.execute("DROP TRIGGER contents_interaction_target_insert ON public.contents")
    op.execute("DROP FUNCTION public.contents_interaction_target_insert()")
    op.drop_table("interaction_targets")
