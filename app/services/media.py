"""Xử lý upload media: validate MIME/size, lấy dimensions, lưu qua storage."""

import io
import uuid

import filetype
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.media import Media
from app.services.storage import get_storage

settings = get_settings()

_IMAGE_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
_VIDEO_EXT = {"video/mp4": "mp4", "video/webm": "webm"}


def _ensure_size(size: int, limit: int) -> None:
    if size > limit:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File vượt giới hạn {limit // (1024 * 1024)}MB",
        )


def _image_dimensions(data: bytes) -> tuple[int, int]:
    try:
        # verify() kiểm tra toàn vẹn nhưng khiến ảnh không dùng lại được → mở 2 lần
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            return img.size
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File ảnh hỏng hoặc không hợp lệ",
        ) from exc


async def create_media(
    session: AsyncSession, file: UploadFile, alt_text: str | None = None
) -> Media:
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File rỗng"
        )

    # Xác định MIME từ NỘI DUNG (magic bytes), không tin đuôi file.
    kind = filetype.guess(data)
    mime = kind.mime if kind else None

    if mime in settings.allowed_image_types:
        _ensure_size(len(data), settings.max_image_size)
        width, height = _image_dimensions(data)
        duration = None
        ext = _IMAGE_EXT[mime]
    elif mime in settings.allowed_video_types:
        _ensure_size(len(data), settings.max_video_size)
        # Dimensions/duration video cần ffprobe — bổ sung ở bước sau.
        width = height = duration = None
        ext = _VIDEO_EXT[mime]
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Định dạng không được hỗ trợ: {mime or 'không xác định'}",
        )

    key = f"{uuid.uuid4().hex}.{ext}"
    get_storage().save(key, data)

    media = Media(
        storage_key=key,
        mime_type=mime,
        size=len(data),
        width=width,
        height=height,
        duration=duration,
        alt_text=alt_text,
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)
    return media


async def delete_media(session: AsyncSession, media: Media) -> None:
    get_storage().delete(media.storage_key)
    await session.delete(media)
    await session.commit()
