"""Cấu hình production và khởi động PM2; không in giá trị bí mật."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import get_origin
from uuid import uuid4

from dotenv import dotenv_values
from pydantic import ValidationError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.config import Settings
from app.services.drive_metadata import drive_id


def settings_from_env(path: Path = Path(".env")) -> Settings:
    # Giá trị trong file deploy ưu tiên biến còn sót lại trong môi trường runner.
    values = {
        key.lower(): value
        for key, value in dotenv_values(path).items()
        if value is not None
    }
    for name, field in Settings.model_fields.items():
        if name in values and get_origin(field.annotation) in (list, dict):
            values[name] = json.loads(values[name])
    return Settings(_env_file=None, **values)


def public_origin(value: str) -> str:
    from urllib.parse import urlsplit

    url = urlsplit(value)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.path not in ("", "/")
        or url.query
        or url.fragment
    ):
        raise ValueError("PUBLIC_SITE_URL phải là origin HTTPS, không kèm đường dẫn")
    return f"https://{url.netloc}"


def configure(path: Path = Path(".env")) -> None:
    if path.is_symlink():
        raise ValueError("Cần cấu hình trực tiếp file .env thường, không qua symlink")
    current = settings_from_env(path)
    key = os.environ.get("DEPLOY_GOOGLE_DRIVE_API_KEY") or current.google_drive_api_key
    account_json = os.environ.get("DEPLOY_GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "")
    account = None
    if account_json:
        try:
            account = json.loads(account_json)
            if (
                not isinstance(account, dict)
                or account.get("type") != "service_account"
                or account.get("token_uri") != "https://oauth2.googleapis.com/token"
                or not account.get("client_email", "").endswith(".gserviceaccount.com")
                or not account.get("private_key", "").startswith(
                    "-----BEGIN PRIVATE KEY-----"
                )
            ):
                raise ValueError
        except (ValueError, AttributeError):
            raise ValueError("Thông tin service account Drive không hợp lệ") from None
    account_file = current.google_drive_service_account_file
    if not (key or account or account_file):
        raise ValueError("Cần API key hoặc service account chỉ đọc cho Drive")
    jwt = current.jwt_secret
    rotate_jwt = jwt == "change-me-in-production" or len(jwt) < 32
    if rotate_jwt:
        jwt = os.environ.get("DEPLOY_JWT_SECRET", "")
        if len(jwt) < 32 or jwt == "change-me-in-production":
            raise ValueError("Chưa có JWT_SECRET đủ mạnh cho deploy")
    folder = drive_id(
        os.environ.get("DEPLOY_GOOGLE_DRIVE_FOLDER_ID")
        or current.google_drive_folder_id
    )
    updates = {
        "ENVIRONMENT": "prod",
        "PUBLIC_CONTENT_SOURCE": "drive",
        "GOOGLE_DRIVE_API_KEY": key,
        "GOOGLE_DRIVE_FOLDER_ID": folder,
        "DRIVE_CATALOG_CACHE_SECONDS": str(
            min(current.drive_catalog_cache_seconds, 15)
        ),
        "JWT_SECRET": jwt,
    }
    database = os.environ.get("DEPLOY_DATABASE_URL", "").strip()
    if database:
        try:
            url = make_url(database)
        except ArgumentError:
            raise ValueError("DATABASE_URL deploy không hợp lệ") from None
        if url.drivername != "postgresql+asyncpg" or not url.host:
            raise ValueError("DATABASE_URL deploy cần PostgreSQL với driver asyncpg")
        updates["DATABASE_URL"] = database
    site = os.environ.get("DEPLOY_PUBLIC_SITE_URL", "").strip()
    if site:
        origin = public_origin(site)
        updates["CORS_ORIGINS"] = json.dumps([origin])

    if account:
        credential_dir = path.parent / ".local" / "credentials"
        credential_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        if credential_dir.is_symlink():
            raise ValueError("Thư mục credential không được dùng symlink")
        # Versioned file: failed deploy leaves the previous credential usable.
        credential_path = credential_dir / f"drive-{uuid4().hex}.json"
        with credential_path.open("x", encoding="utf-8") as credential:
            os.chmod(credential_path, 0o600)
            json.dump(account, credential)
        updates["GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE"] = str(credential_path.resolve())

    before = path.read_bytes() if path.exists() else b""
    text = before.decode("utf-8-sig")
    remaining = set(updates)
    lines = []
    for line in text.splitlines():
        match = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        name = match.group(1) if match else None
        if name in updates:
            lines.append(f"{name}={json.dumps(updates[name])}")
            remaining.discard(name)
        else:
            lines.append(line)
    lines.extend(f"{name}={json.dumps(updates[name])}" for name in sorted(remaining))

    backup_dir = path.parent / ".local" / "deploy-backups" / f"config-{uuid4().hex}"
    backup_dir.mkdir(parents=True, mode=0o700)
    if before:
        backup = backup_dir / "environment.backup"
        backup.write_bytes(before)
        backup.chmod(0o600)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".env.", delete=False
        ) as file:
            temporary = Path(file.name)
            file.write("\n".join(lines) + "\n")
        temporary.chmod(0o600)
        validated = settings_from_env(temporary)
        if validated.public_content_source != "drive" or not validated.is_prod:
            raise ValueError("Cấu hình deploy không hợp lệ")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print("Đã lưu cấu hình production; bản sao .env nằm trong .local/deploy-backups.")
    if rotate_jwt:
        print("Đã thay JWT secret yếu; các phiên cũ cần đăng nhập lại.")
    if site:
        print("Đã cấu hình origin HTTPS cho đăng nhập và WebSocket.")


def application_environment(settings: Settings) -> dict[str, str]:
    values = {
        name.upper(): json.dumps(value)
        if isinstance(value, list | dict)
        else str(value)
        for name, value in settings.model_dump().items()
    }
    # PM2 daemon phải tiếp tục chạy sau khi GitHub Actions kết thúc job.
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("DEPLOY_", "GITHUB_", "ACTIONS_", "RUNNER_"))
    }
    env.update(values)
    env["RUNNER_TRACKING_ID"] = ""
    return env


def migrate(path: Path = Path(".env")) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env=application_environment(settings_from_env(path)),
    )


def restart(path: Path = Path(".env")) -> None:
    subprocess.run(
        [
            "pm2",
            "startOrReload",
            "ecosystem.config.cjs",
            "--only",
            "eskeylation-api",
            "--update-env",
        ],
        check=True,
        env=application_environment(settings_from_env(path)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["configure", "migrate", "restart"])
    args = parser.parse_args()
    try:
        if args.action == "configure":
            configure()
        elif args.action == "migrate":
            migrate()
        else:
            restart()
    except ValidationError as error:
        fields = {str(part) for item in error.errors() for part in item["loc"]}
        raise SystemExit(
            "Cấu hình không hợp lệ: " + ", ".join(sorted(fields))
        ) from None
    except ValueError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
