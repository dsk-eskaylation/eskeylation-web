from collections.abc import AsyncGenerator

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Supabase Transaction pooler (PgBouncer, cổng 6543) đã tự pool kết nối,
# nên SQLAlchemy dùng NullPool để không pool chồng. Tắt prepared statement
# cache của asyncpg cho tương thích PgBouncer.
engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
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
