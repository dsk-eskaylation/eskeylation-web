"""Bảo mật: pin search_path cho hàm + chuyển extension unaccent khỏi public.

Xử lý 2 cảnh báo của Supabase advisor:
- "Function Search Path Mutable" (f_unaccent, contents_search_tsv,
  contents_search_vector_update): hàm không cố định search_path -> nguy cơ
  search_path injection. Pin search_path tường minh cho từng hàm.
- "Extension in Public" (unaccent): chuyển extension sang schema `extensions`
  riêng theo khuyến nghị Supabase. f_unaccent trỏ tới extensions qua search_path.

Revision ID: j7e5g2b4d6f0
Revises: i6d4f1a3c5e9
Create Date: 2026-07-13
"""

from typing import Sequence, Union

from alembic import op

revision: str = "j7e5g2b4d6f0"
down_revision: Union[str, Sequence[str], None] = "i6d4f1a3c5e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Chuyển extension unaccent ra khỏi public (schema extensions đã có sẵn trên
    # Supabase; tạo phòng hờ). Ứng dụng chỉ gọi qua f_unaccent nên trong suốt.
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute("GRANT USAGE ON SCHEMA extensions TO public")
    op.execute("ALTER EXTENSION unaccent SET SCHEMA extensions")

    # f_unaccent: search_path trỏ extensions (nơi unaccent + dictionary cư trú)
    op.execute(
        "CREATE OR REPLACE FUNCTION public.f_unaccent(text) RETURNS text "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT "
        "SET search_path = extensions, pg_catalog AS "
        "$$ SELECT unaccent('unaccent', $1) $$"
    )
    # contents_search_tsv: dùng public.f_unaccent + to_tsvector (pg_catalog)
    op.execute(
        "CREATE OR REPLACE FUNCTION public.contents_search_tsv("
        "p_title text, p_summary text, p_body jsonb) RETURNS tsvector "
        "LANGUAGE sql IMMUTABLE SET search_path = public, pg_catalog AS "
        "$$ SELECT to_tsvector('simple', public.f_unaccent("
        "coalesce(p_title,'') || ' ' || coalesce(p_summary,'') || ' ' || "
        "coalesce(p_body::text,''))) $$"
    )
    # contents_search_vector_update: trigger fn, gọi public.contents_search_tsv
    op.execute(
        "CREATE OR REPLACE FUNCTION public.contents_search_vector_update() "
        "RETURNS trigger LANGUAGE plpgsql "
        "SET search_path = public, pg_catalog AS "
        "$$ BEGIN NEW.search_vector := public.contents_search_tsv("
        "NEW.title, NEW.summary, NEW.body); RETURN NEW; END $$"
    )


def downgrade() -> None:
    # Khôi phục: bỏ pin search_path + đưa extension về public
    op.execute(
        "CREATE OR REPLACE FUNCTION public.contents_search_vector_update() "
        "RETURNS trigger LANGUAGE plpgsql AS "
        "$$ BEGIN NEW.search_vector := contents_search_tsv("
        "NEW.title, NEW.summary, NEW.body); RETURN NEW; END $$"
    )
    op.execute(
        "CREATE OR REPLACE FUNCTION public.contents_search_tsv("
        "p_title text, p_summary text, p_body jsonb) RETURNS tsvector "
        "LANGUAGE sql IMMUTABLE AS "
        "$$ SELECT to_tsvector('simple', f_unaccent("
        "coalesce(p_title,'') || ' ' || coalesce(p_summary,'') || ' ' || "
        "coalesce(p_body::text,''))) $$"
    )
    op.execute("ALTER EXTENSION unaccent SET SCHEMA public")
    op.execute(
        "CREATE OR REPLACE FUNCTION public.f_unaccent(text) RETURNS text "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS "
        "$$ SELECT unaccent('unaccent', $1) $$"
    )
