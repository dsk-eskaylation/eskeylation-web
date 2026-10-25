from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình ứng dụng, đọc từ biến môi trường / file .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Kết nối Supabase (PostgreSQL) qua connection pooler (PgBouncer).
    # Dùng driver asyncpg cho SQLAlchemy async.
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/postgres"

    # Celery / Redis
    redis_url: str = "redis://localhost:6379/0"
    media_processing_enabled: bool = False

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60 * 12, ge=5, le=1440)

    # S3 giữ bucket riêng tư; URL public được phục vụ qua CloudFront OAC.
    storage_backend: Literal["local", "supabase", "s3"] = "local"
    media_root: str = "media"  # dùng khi backend = local

    s3_bucket: str = ""
    s3_region: str = "ap-southeast-2"
    s3_cdn_url: str = ""
    # Tách file CMS khỏi các file tải thử/thư mục khác trong cùng bucket.
    s3_key_prefix: str = "cms"
    s3_probe_key: str = "migration-ready.json"
    aws_access_key_id: str = Field(default="", repr=False)
    aws_secret_access_key: str = Field(default="", repr=False)

    # Supabase Storage (khi backend = supabase). Bucket nên đặt public để có CDN URL.
    supabase_url: str = ""  # https://<project-ref>.supabase.co
    supabase_service_key: str = ""  # service_role key
    storage_bucket: str = "media"

    # Upload media — giới hạn size (byte) và MIME được phép.
    max_image_size: int = 10 * 1024 * 1024  # 10 MB
    max_video_size: int = 200 * 1024 * 1024  # 200 MB
    max_audio_size: int = 100 * 1024 * 1024  # 100 MB
    allowed_image_types: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    ]
    allowed_video_types: list[str] = ["video/mp4", "video/webm"]
    allowed_audio_types: list[str] = ["audio/mpeg"]
    # Chỉ dùng phía server/CLI, không đưa vào frontend.
    google_drive_api_key: str = ""
    google_drive_service_account_file: str = ""
    public_content_source: Literal["database", "drive"] = "database"
    google_drive_folder_id: str = "1lnfNK-1UMVLrydMHBntY33cLipf4MyFL"
    drive_catalog_cache_seconds: int = Field(default=15, ge=0, le=3600)
    drive_image_cache_bytes: int = Field(
        default=32 * 1024 * 1024, ge=0, le=128 * 1024 * 1024
    )
    drive_max_image_bytes: int = Field(
        default=32 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024
    )
    drive_stream_concurrency: int = Field(default=16, ge=1, le=64)

    # CORS — origin của frontend (React/Vite). Khai báo JSON list trong .env.
    cors_origins: list[str] = ["http://localhost:5173"]

    # Môi trường: "dev" | "prod" — ảnh hưởng log, cookie Secure, guard secret.
    environment: str = "dev"

    @property
    def is_prod(self) -> bool:
        """FAIL-SAFE: mọi giá trị KHÔNG PHẢI 'dev' đều coi là prod — tránh
        đặt ENVIRONMENT=production/PROD/staging... làm guard bảo mật fail-open."""
        return self.environment.strip().lower() != "dev"

    # Bảo mật nội dung — tag/attribute HTML an toàn cho rich text (bleach).
    allowed_html_tags: list[str] = [
        "p",
        "br",
        "b",
        "strong",
        "i",
        "em",
        "u",
        "s",
        "ul",
        "ol",
        "li",
        "a",
        "blockquote",
        "code",
        "pre",
        "h2",
        "h3",
        "h4",
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
        "soundcloud.com",
        "m.soundcloud.com",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
