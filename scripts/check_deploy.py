"""Kiểm tra cấu hình backend trên máy deploy; không in giá trị bí mật."""

import argparse
import asyncio
import json
import os

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.services.storage import S3Storage
from scripts.deploy import settings_from_env


async def check_database(settings: Settings) -> None:
    url = make_url(settings.database_url)
    info = {"database_host": url.host, "database_port": url.port}
    if os.environ.get("DATABASE_URL"):
        try:
            inherited = make_url(os.environ["DATABASE_URL"])
            info["runner_uses_different_host"] = inherited.host != url.host
        except ValueError:
            info["runner_has_invalid_database_url"] = True
    print(json.dumps(info), flush=True)
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0, "timeout": 12},
    )
    try:
        async with asyncio.timeout(15), engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        print("Kết nối database production thành công.")
    except Exception as error:
        raise SystemExit(
            f"Không kết nối được database ({type(error).__name__}); "
            "kiểm tra DATABASE_URL, DNS và quyền truy cập mạng."
        ) from None
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", action="store_true")
    args = parser.parse_args()
    settings = settings_from_env()
    missing = []
    if settings.public_content_source == "drive" and not (
        settings.google_drive_api_key or settings.google_drive_service_account_file
    ):
        missing.append("GOOGLE_DRIVE_API_KEY hoặc GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE")
    if (
        settings.public_content_source == "drive"
        and not settings.google_drive_folder_id
    ):
        missing.append("GOOGLE_DRIVE_FOLDER_ID")
    if settings.storage_backend == "s3":
        try:
            S3Storage(
                settings.s3_bucket,
                settings.s3_region,
                settings.s3_cdn_url,
                settings.s3_key_prefix,
            )
        except ValueError:
            missing.append("S3_BUCKET / S3_REGION / S3_CDN_URL")
        if not (settings.aws_access_key_id and settings.aws_secret_access_key):
            missing.append("AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY")
    if (
        settings.jwt_secret == "change-me-in-production"
        or len(settings.jwt_secret) < 32
    ):
        missing.append("JWT_SECRET (ít nhất 32 ký tự)")
    if "@localhost:5432/postgres" in settings.database_url:
        missing.append("DATABASE_URL")
    if missing:
        raise SystemExit("Cấu hình deploy còn thiếu: " + ", ".join(missing))
    print("Cấu hình nguồn nội dung, storage và tài khoản đã sẵn sàng.")
    if args.database:
        asyncio.run(check_database(settings))


if __name__ == "__main__":
    main()
