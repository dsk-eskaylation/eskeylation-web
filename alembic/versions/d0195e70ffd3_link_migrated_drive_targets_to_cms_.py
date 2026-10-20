"""link migrated drive targets to cms content

Revision ID: d0195e70ffd3
Revises: 3d01facc19af
Create Date: 2026-10-20 13:53:38.775084

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0195e70ffd3'
down_revision: Union[str, Sequence[str], None] = '3d01facc19af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_constraint("ck_interaction_targets_source", "interaction_targets", type_="check")
    op.create_check_constraint(
        "ck_interaction_targets_source", "interaction_targets",
        "(id > 0 AND content_id IS NOT NULL AND content_id = id "
        "AND drive_file_id IS NULL) OR (id < 0 AND drive_file_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM public.interaction_targets "
        "WHERE id < 0 AND content_id IS NOT NULL) THEN "
        "RAISE EXCEPTION 'Unlink migrated S3 content before downgrade'; END IF; END $$"
    )
    op.drop_constraint("ck_interaction_targets_source", "interaction_targets", type_="check")
    op.create_check_constraint(
        "ck_interaction_targets_source", "interaction_targets",
        "(id > 0 AND content_id IS NOT NULL AND content_id = id "
        "AND drive_file_id IS NULL) OR "
        "(id < 0 AND content_id IS NULL AND drive_file_id IS NOT NULL)",
    )
