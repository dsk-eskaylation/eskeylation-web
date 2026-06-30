"""Celery task xử lý media nền.

LƯU Ý: cần Redis + worker (`celery -A app.workers.celery_app worker`) mới chạy.
Chưa auto-trigger sau upload — kích hoạt khi hạ tầng Celery sẵn sàng (Phase 5 đầy đủ).
"""

import io

from PIL import Image

from app.services.storage import get_storage
from app.workers.celery_app import celery_app

THUMBNAIL_SIZE = (400, 400)


@celery_app.task(name="media.generate_thumbnail")
def generate_thumbnail(storage_key: str) -> str:
    """Tạo thumbnail từ ảnh gốc, lưu cạnh ảnh gốc, trả về key thumbnail."""
    storage = get_storage()
    data = storage.read(storage_key)

    with Image.open(io.BytesIO(data)) as img:
        img.thumbnail(THUMBNAIL_SIZE)
        buffer = io.BytesIO()
        img.save(buffer, format=img.format or "PNG")
        thumb_data = buffer.getvalue()

    stem, _, ext = storage_key.rpartition(".")
    thumb_key = f"{stem}_thumb.{ext}"
    storage.save(thumb_key, thumb_data)
    return thumb_key
