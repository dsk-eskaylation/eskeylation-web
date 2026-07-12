"""Bảo mật: policy deny-all tường minh cho các bảng public (advisor RLS No Policy).

Kiến trúc: backend FastAPI kết nối bằng role owner (postgres) -> BỎ QUA RLS;
frontend KHÔNG gọi thẳng Supabase (CSP connect-src 'self'). RLS bật + không policy
đã là "từ chối mọi truy cập qua PostgREST (anon/authenticated)", nhưng Supabase
advisor cảnh báo "RLS Enabled No Policy". Thêm policy deny-all tường minh (USING
false) để: (1) ghi rõ chủ đích khoá chặt, (2) làm sạch advisor. KHÔNG đổi hành vi
— owner vẫn bypass (forcerowsecurity=false), anon/authenticated vẫn bị từ chối.

Revision ID: k8f6h3c5e7g1
Revises: j7e5g2b4d6f0
Create Date: 2026-07-13
"""

from typing import Sequence, Union

from alembic import op

revision: str = "k8f6h3c5e7g1"
down_revision: Union[str, Sequence[str], None] = "j7e5g2b4d6f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mọi bảng public đang RLS-bật-không-policy
_TABLES = [
    "activity_logs",
    "alembic_version",
    "banned_words",
    "comment_reactions",
    "comments",
    "content_media",
    "contents",
    "lyric_suggestions",
    "media",
    "post_reactions",
    "saved_posts",
    "users",
]


def upgrade() -> None:
    for t in _TABLES:
        op.execute(f'DROP POLICY IF EXISTS deny_all ON public."{t}"')
        # PERMISSIVE FOR ALL TO public USING(false): không hàng nào qua được cho
        # mọi role thường; owner (backend) bypass vì RLS không FORCE.
        op.execute(
            f'CREATE POLICY deny_all ON public."{t}" '
            "AS PERMISSIVE FOR ALL TO public "
            "USING (false) WITH CHECK (false)"
        )


def downgrade() -> None:
    for t in _TABLES:
        op.execute(f'DROP POLICY IF EXISTS deny_all ON public."{t}"')
