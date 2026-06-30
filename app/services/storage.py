"""Storage abstraction. Mọi truy cập media đi qua interface này.

LocalStorage cho dev; SupabaseStorage cho prod (S3-compatible + CDN). Đổi backend
bằng setting storage_backend — service/router KHÔNG gọi thẳng SDK Supabase.
"""

import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from app.config import get_settings


class Storage(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes) -> str:
        """Lưu nội dung theo key, trả về URL truy cập."""

    @abstractmethod
    def url(self, key: str) -> str:
        """Trả về URL ổn định cho key."""

    @abstractmethod
    def read(self, key: str) -> bytes:
        """Đọc nội dung theo key."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Xoá nội dung theo key (bỏ qua nếu không tồn tại)."""


class LocalStorage(Storage):
    """Lưu file xuống thư mục cục bộ (chỉ dùng cho dev)."""

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def save(self, key: str, data: bytes) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.url(key)

    def url(self, key: str) -> str:
        return f"/{self.root.as_posix()}/{key}"

    def read(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def delete(self, key: str) -> None:
        (self.root / key).unlink(missing_ok=True)


class SupabaseStorage(Storage):
    """Lưu media trên Supabase Storage qua REST API (bucket nên public để có CDN)."""

    def __init__(self, base_url: str, service_key: str, bucket: str) -> None:
        base = base_url.rstrip("/")
        self._api = f"{base}/storage/v1"
        self._public_base = f"{base}/storage/v1/object/public/{bucket}"
        self._bucket = bucket
        self._headers = {
            "Authorization": f"Bearer {service_key}",
            "apikey": service_key,
        }

    def save(self, key: str, data: bytes) -> str:
        content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
        resp = httpx.post(
            f"{self._api}/object/{self._bucket}/{key}",
            content=data,
            headers={**self._headers, "Content-Type": content_type, "x-upsert": "true"},
            timeout=30,
        )
        resp.raise_for_status()
        return self.url(key)

    def url(self, key: str) -> str:
        return f"{self._public_base}/{key}"

    def read(self, key: str) -> bytes:
        resp = httpx.get(
            f"{self._api}/object/{self._bucket}/{key}",
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.content

    def delete(self, key: str) -> None:
        resp = httpx.delete(
            f"{self._api}/object/{self._bucket}/{key}",
            headers=self._headers,
            timeout=30,
        )
        if resp.status_code != httpx.codes.NOT_FOUND:
            resp.raise_for_status()


def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "supabase":
        return SupabaseStorage(s.supabase_url, s.supabase_service_key, s.storage_bucket)
    return LocalStorage(s.media_root)
