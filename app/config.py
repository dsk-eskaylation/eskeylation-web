from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình ứng dụng, đọc từ biến môi trường / file .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Kết nối Supabase (PostgreSQL) qua connection pooler (PgBouncer).
    # Dùng driver asyncpg cho SQLAlchemy async.
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/postgres"

    # Celery / Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # Storage cục bộ cho dev (Phase 9 thay bằng Supabase Storage).
    media_root: str = "media"


@lru_cache
def get_settings() -> Settings:
    return Settings()
