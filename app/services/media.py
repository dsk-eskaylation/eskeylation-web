"""Xử lý upload media: validate MIME/size, lấy dimensions, lưu qua storage."""

import io
import logging
import uuid

import filetype
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.models.media import Media
from app.services.media_jobs import queue
from app.services.media_processing import cleanup, derived_keys
from app.services.storage import get_storage

settings = get_settings()
logger = logging.getLogger(__name__)

_IMAGE_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
_VIDEO_EXT = {"video/mp4": "mp4", "video/webm": "webm"}
_AUDIO_EXT = {"audio/mpeg": "mp3"}


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
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File ảnh hỏng hoặc không hợp lệ",
        ) from exc


async def _read_capped(file: UploadFile, cap: int) -> bytes:
    """Đọc upload theo chunk, dừng ngay khi vượt trần — không cho body khổng lồ
    chiếm hết RAM trước khi kịp kiểm tra size."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > cap:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File vượt giới hạn {cap // (1024 * 1024)}MB",
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def create_media(
    session: AsyncSession,
    file: UploadFile,
    alt_text: str | None = None,
    *,
    uploaded_by: int | None = None,
    images_only: bool = False,
) -> Media:
    header = await file.read(261)
    await file.seek(0)
    if not header:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File rỗng")

    # Xác định MIME từ NỘI DUNG (magic bytes), không tin đuôi file.
    kind = filetype.guess(header)
    mime = kind.mime if kind else None
    if images_only and mime not in settings.allowed_image_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Chỉ hỗ trợ ảnh JPG, PNG, WebP hoặc GIF",
        )

    if mime in settings.allowed_image_types:
        data = await _read_capped(file, settings.max_image_size)
        _ensure_size(len(data), settings.max_image_size)
        width, height = await run_in_threadpool(_image_dimensions, data)
        duration = None
        ext = _IMAGE_EXT[mime]
    elif mime in settings.allowed_video_types:
        data = await _read_capped(file, settings.max_video_size)
        _ensure_size(len(data), settings.max_video_size)
        # Dimensions/duration video cần ffprobe — bổ sung ở bước sau.
        width = height = duration = None
        ext = _VIDEO_EXT[mime]
    elif mime in settings.allowed_audio_types:
        data = await _read_capped(file, settings.max_audio_size)
        width = height = duration = None
        ext = _AUDIO_EXT[mime]
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Định dạng không được hỗ trợ: {mime or 'không xác định'}",
        )

    key = f"{uuid.uuid4().hex}.{ext}"
    # storage có thể gọi mạng (Supabase) → chạy trong threadpool, không chặn loop.
    try:
        await run_in_threadpool(get_storage().save, key, data)
    except (BotoCoreError, ClientError) as error:
        # Không đưa AWS request/credential hoặc lỗi nội bộ ra response/log.
        logger.warning("Không lưu được media trên S3 (%s)", type(error).__name__)
        raise HTTPException(
            503, "Tạm thời không lưu được media, vui lòng thử lại"
        ) from None

    media = Media(
        storage_key=key,
        mime_type=mime,
        size=len(data),
        width=width,
        height=height,
        duration=duration,
        alt_text=alt_text,
        uploaded_by=uploaded_by,
    )
    if settings.media_processing_enabled:
        queue(media)
    session.add(media)
    # A lost commit acknowledgement is ambiguous: keep the original rather
    # than risk removing a file referenced by a successfully committed row.
    await session.commit()
    await session.refresh(media)
    return media


async def delete_media(session: AsyncSession, media: Media) -> None:
    """Xoá record DB TRƯỚC rồi mới xoá file storage — nếu xoá file lỗi thì chỉ
    orphan file (dễ dọn), không bao giờ có record trỏ tới file đã mất."""
    storage_key = media.storage_key
    keys = derived_keys(media.variants or {}, media.id) | {storage_key}
    await session.delete(media)
    await session.commit()
    await run_in_threadpool(cleanup, get_storage(), keys)
