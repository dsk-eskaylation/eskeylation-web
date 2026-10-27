"""Notifications when someone reacts to or comments on a user's post or comment."""

from alembic import op
import sqlalchemy as sa

revision = "s8c0e2a4b6d7"
down_revision = "r7b9d1f3a5c6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column(
            "content_id",
            sa.BigInteger(),
            sa.ForeignKey("interaction_targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "comment_id", sa.Integer(), sa.ForeignKey("comments.id", ondelete="CASCADE")
        ),
        sa.Column("read_at", sa.DateTime(timezone=True)),
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
            "kind IN ('post_reaction', 'post_comment', 'comment_reaction')",
            name="ck_notifications_kind",
        ),
    )
    op.create_index(
        "ix_notifications_user_created", "notifications", ["user_id", "created_at"]
    )
    op.execute("ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY deny_all ON public.notifications "
        "AS PERMISSIVE FOR ALL TO public USING (false) WITH CHECK (false)"
    )
    op.execute(
        """DO $$ DECLARE role_name text; BEGIN
        FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = role_name) THEN
                EXECUTE format('REVOKE ALL ON TABLE public.notifications FROM %I',
                               role_name);
            END IF;
        END LOOP;
        END $$"""
    )


def downgrade():
    op.drop_table("notifications")
