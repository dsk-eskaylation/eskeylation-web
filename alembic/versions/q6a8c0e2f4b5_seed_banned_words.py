"""Seed the banned words listed in the product spec.

Existing rows are kept, so words an admin already added or removed later are
never overwritten by re-running this migration.
"""

from alembic import op

revision = "q6a8c0e2f4b5"
down_revision = "p5f7b9d1e3a4"
branch_labels = None
depends_on = None

WORDS = ["địt", "lồn", "cặc", "buồi", "đĩ", "óc chó", "ngu", "đít", "vú", "đm", "địt mẹ"]


def upgrade():
    for word in WORDS:
        op.execute(
            f"INSERT INTO banned_words (word, created_at, updated_at) "
            f"VALUES ('{word}', now(), now()) ON CONFLICT (word) DO NOTHING"
        )


def downgrade():
    pass
