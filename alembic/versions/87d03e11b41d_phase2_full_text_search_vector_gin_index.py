"""phase2: full-text search vector + gin index

Revision ID: 87d03e11b41d
Revises: 4750def72355
Create Date: 2026-06-22 22:58:56.726929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '87d03e11b41d'
down_revision: Union[str, Sequence[str], None] = '4750def72355'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # unaccent + wrapper IMMUTABLE (dùng dictionary tường minh để an toàn mark IMMUTABLE)
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute(
        "CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS "
        "$$ SELECT unaccent('unaccent', $1) $$"
    )

    # Hàm build tsvector dùng chung cho cả trigger lẫn backfill
    op.execute(
        "CREATE OR REPLACE FUNCTION contents_search_tsv("
        "p_title text, p_summary text, p_body jsonb) RETURNS tsvector "
        "LANGUAGE sql IMMUTABLE AS $$ SELECT to_tsvector('simple', f_unaccent("
        "coalesce(p_title,'') || ' ' || coalesce(p_summary,'') || ' ' || "
        "coalesce(p_body::text,''))) $$"
    )

    op.add_column(
        "contents", sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True)
    )

    # Trigger cập nhật search_vector khi đổi title/summary/body
    op.execute(
        "CREATE OR REPLACE FUNCTION contents_search_vector_update() "
        "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "NEW.search_vector := contents_search_tsv(NEW.title, NEW.summary, NEW.body); "
        "RETURN NEW; END $$"
    )
    op.execute(
        "CREATE TRIGGER contents_search_vector_trigger "
        "BEFORE INSERT OR UPDATE OF title, summary, body ON contents "
        "FOR EACH ROW EXECUTE FUNCTION contents_search_vector_update()"
    )

    # Backfill cho dữ liệu sẵn có
    op.execute(
        "UPDATE contents SET search_vector = "
        "contents_search_tsv(title, summary, body)"
    )

    op.create_index(
        "ix_contents_search_vector",
        "contents",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_contents_search_vector", table_name="contents", postgresql_using="gin"
    )
    op.execute("DROP TRIGGER IF EXISTS contents_search_vector_trigger ON contents")
    op.execute("DROP FUNCTION IF EXISTS contents_search_vector_update()")
    op.drop_column("contents", "search_vector")
    op.execute("DROP FUNCTION IF EXISTS contents_search_tsv(text, text, jsonb)")
    op.execute("DROP FUNCTION IF EXISTS f_unaccent(text)")
