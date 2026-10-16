"""phien dang nhap co the thu hoi va role thanh vien

Revision ID: 3d01facc19af
Revises: l9a7b4d6f8h2
Create Date: 2026-10-16 15:36:03.839625

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3d01facc19af"
down_revision: Union[str, Sequence[str], None] = "l9a7b4d6f8h2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role", "users", "role IN ('admin', 'editor', 'author', 'member')"
    )
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])
    op.execute("ALTER TABLE public.user_sessions ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY deny_all ON public.user_sessions FOR ALL TO public "
        "USING (false) WITH CHECK (false)"
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM public.users WHERE role='member') "
        "THEN RAISE EXCEPTION 'Migrate member accounts before downgrade'; "
        "END IF; END $$"
    )
    op.drop_table("user_sessions")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role", "users", "role IN ('admin', 'editor', 'author')"
    )
