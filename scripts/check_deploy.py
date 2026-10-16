"""Kiểm tra cấu hình backend trên máy deploy; không in giá trị bí mật."""

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    missing = []
    if settings.public_content_source != "drive":
        missing.append("PUBLIC_CONTENT_SOURCE=drive")
    if not settings.google_drive_api_key:
        missing.append("GOOGLE_DRIVE_API_KEY")
    if not settings.google_drive_folder_id:
        missing.append("GOOGLE_DRIVE_FOLDER_ID")
    if (
        settings.jwt_secret == "change-me-in-production"
        or len(settings.jwt_secret) < 32
    ):
        missing.append("JWT_SECRET (ít nhất 32 ký tự)")
    if "@localhost:5432/postgres" in settings.database_url:
        missing.append("DATABASE_URL")
    if missing:
        raise SystemExit("Cấu hình deploy còn thiếu: " + ", ".join(missing))
    print("Cấu hình Drive và tài khoản đã sẵn sàng.")


if __name__ == "__main__":
    main()
