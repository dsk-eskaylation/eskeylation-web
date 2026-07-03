"""Bật Row Level Security cho mọi bảng schema public.

Supabase expose PostgREST (/rest/v1) với anon key: bảng public không RLS
sẽ bị đọc/ghi tự do qua Data API. Bật RLS mà KHÔNG tạo policy = chặn toàn bộ
truy cập anon/authenticated qua REST. Backend FastAPI + Alembic kết nối
bằng role postgres (table owner, bypass RLS) nên không ảnh hưởng.

Revision ID: c7e21a5f9d03
Revises: a1c9f3d27b64
Create Date: 2026-07-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c7e21a5f9d03"
down_revision: Union[str, Sequence[str], None] = "a1c9f3d27b64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("users", "contents", "media", "content_media", "alembic_version")


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
