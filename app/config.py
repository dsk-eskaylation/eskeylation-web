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

    # Storage: "local" (dev) | "supabase" (prod, dùng Supabase Storage + CDN).
    storage_backend: str = "local"
    media_root: str = "media"  # dùng khi backend = local

    # Supabase Storage (khi backend = supabase). Bucket nên đặt public để có CDN URL.
    supabase_url: str = ""  # https://<project-ref>.supabase.co
    supabase_service_key: str = ""  # service_role key
    storage_bucket: str = "media"

    # Upload media — giới hạn size (byte) và MIME được phép.
    max_image_size: int = 10 * 1024 * 1024  # 10 MB
    max_video_size: int = 200 * 1024 * 1024  # 200 MB
    allowed_image_types: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    ]
    allowed_video_types: list[str] = ["video/mp4", "video/webm"]

    # CORS — origin của frontend (React/Vite). Khai báo JSON list trong .env.
    cors_origins: list[str] = ["http://localhost:5173"]

    # Môi trường: "dev" | "prod" — ảnh hưởng log, hiển thị lỗi.
    environment: str = "dev"

    # Bảo mật nội dung — tag/attribute HTML an toàn cho rich text (bleach).
    allowed_html_tags: list[str] = [
        "p", "br", "b", "strong", "i", "em", "u", "s",
        "ul", "ol", "li", "a", "blockquote", "code", "pre", "h2", "h3", "h4",
    ]
    allowed_html_attributes: dict[str, list[str]] = {
        "a": ["href", "title", "rel"],
    }
    # Host được phép cho embed video (chống SSRF / iframe lạ).
    allowed_embed_hosts: list[str] = [
        "youtube.com",
        "www.youtube.com",
        "youtu.be",
        "vimeo.com",
        "player.vimeo.com",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
