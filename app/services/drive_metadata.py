"""Nhận diện tên và nhóm nội dung từ thư mục Drive công khai."""

import re
from urllib.parse import urlparse

FOLDER_MIME = "application/vnd.google-apps.folder"
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{10,200}")


def drive_id(value: str) -> str:
    if value.startswith("https://"):
        parsed = urlparse(value)
        if parsed.hostname != "drive.google.com":
            raise ValueError("Chỉ nhận URL thư mục drive.google.com")
        value = parsed.path.rstrip("/").split("/")[-1]
    if not ID_PATTERN.fullmatch(value):
        raise ValueError("ID Google Drive không hợp lệ")
    return value


def describe_file(file: dict, folders: list[str]) -> dict:
    """Không suy đoán nghệ sĩ, thể loại nhạc hoặc ngày xuất bản còn thiếu."""
    name = file["name"]
    title = re.sub(
        r"\.(mp3|mp4|mov|webm|jpe?g|png|webp|gif|heic|heif)$",
        "",
        name,
        flags=re.IGNORECASE,
    )
    title = title.removeprefix("Bản sao của ").strip()
    if "Cộng đồng" in folders:
        content_type = "community"
    elif "Video" in folders:
        content_type = "video"
    elif "Nhạc & MV" in folders:
        content_type = "video" if file["mimeType"].startswith("video/") else "music"
    elif "Ảnh" in folders:
        content_type = "gallery"
    else:
        content_type = None
    artist = None
    if content_type == "music":
        title_part, separator, artist_part = title.rpartition(" - ")
        if separator:
            title, artist = title_part.strip(), artist_part.strip()
    mime = file["mimeType"]
    supported = mime in {
        "audio/mpeg",
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/heif",
        "image/heic",
    }
    return {
        "file_id": file["id"],
        "mime_type": mime,
        "type": content_type,
        "title": title[:255],
        "artist": artist,
        "include": supported and bool(content_type),
    }
