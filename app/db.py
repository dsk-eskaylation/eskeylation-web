from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Supabase Transaction pooler (PgBouncer, cổng 6543). Vẫn POOL Ở CLIENT:
# PgBouncer chỉ pool phía server — client dùng NullPool sẽ trả giá TCP+TLS
# handshake (~400ms tới region xa) cho MỖI request, làm mọi endpoint chậm.
# Giữ kết nối client bền + PgBouncer ghép transaction phía sau là mô hình chuẩn.
# Bắt buộc statement_cache_size=0 (prepared statement không sống được qua
# transaction-mode PgBouncer).
engine = create_async_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_recycle=300,  # tái tạo kết nối cũ >5 phút (pooler/firewall hay cắt ngầm)
    pool_pre_ping=True,  # phát hiện kết nối chết trước khi dùng
    connect_args={"statement_cache_size": 0},
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Dependency cấp session; rollback nếu request lỗi để không treo transaction."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
