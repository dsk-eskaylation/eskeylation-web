"""Storage abstraction. Mọi truy cập media đi qua interface này.

LocalStorage cho dev; SupabaseStorage hoặc S3Storage cho media production.
Đổi backend bằng setting storage_backend; router không gọi trực tiếp SDK.
"""

import mimetypes
import re
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlsplit

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

    def download(self, key: str, destination: Path, max_bytes: int) -> None:
        """Bounded fallback for adapters; network adapters stream to disk."""
        data = self.read(key)
        if len(data) > max_bytes:
            raise ValueError("Media exceeds processing limit")
        destination.write_bytes(data)


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
        # MEDIA_ROOT là đường dẫn ổ đĩa; route StaticFiles luôn là /media.
        return f"/media/{quote(key, safe='/')}"

    def read(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def delete(self, key: str) -> None:
        (self.root / key).unlink(missing_ok=True)

    def download(self, key: str, destination: Path, max_bytes: int) -> None:
        with (self.root / key).open("rb") as source:
            _copy_chunks(
                iter(lambda: source.read(1024 * 1024), b""), destination, max_bytes
            )


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

    def download(self, key: str, destination: Path, max_bytes: int) -> None:
        with httpx.stream(
            "GET",
            f"{self._api}/object/{self._bucket}/{key}",
            headers=self._headers,
            timeout=30,
        ) as response:
            response.raise_for_status()
            _copy_chunks(response.iter_bytes(1024 * 1024), destination, max_bytes)


@lru_cache(maxsize=8)
def _s3_client(region: str):
    # Chỉ khởi tạo trong threadpool khi đọc/ghi, không gọi credential provider
    # trong lúc serialize URL trên event loop. Tái sử dụng connection pool.
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=get_settings().aws_access_key_id or None,
        aws_secret_access_key=get_settings().aws_secret_access_key or None,
        config=Config(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=30,
            retries={"mode": "standard", "total_max_attempts": 3},
        ),
    )


class S3Storage(Storage):
    """Backend-only AWS credentials; CloudFront chỉ được quyền đọc qua OAC."""

    def __init__(
        self, bucket: str, region: str, cdn_url: str, prefix: str = "cms"
    ) -> None:
        parsed = urlsplit(cdn_url)
        if (
            not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket)
            or not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d", region)
            or parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Cần cấu hình S3 bucket, region và origin CDN HTTPS hợp lệ"
            )
        self.bucket = bucket
        self.region = region
        self.cdn_url = cdn_url.rstrip("/")
        self.prefix = prefix.strip("/")
        if self.prefix:
            self._validate_key(self.prefix)

    @staticmethod
    def _validate_key(key: str) -> None:
        if (
            not key
            or len(key.encode("utf-8")) > 1024
            or "\\" in key
            or any(ord(char) < 32 or ord(char) == 127 for char in key)
            or any(part in {"", ".", ".."} for part in key.split("/"))
        ):
            raise ValueError("Storage key không hợp lệ")

    def _key(self, key: str) -> str:
        self._validate_key(key)
        full_key = f"{self.prefix}/{key}" if self.prefix else key
        self._validate_key(full_key)
        return full_key

    def save(self, key: str, data: bytes) -> str:
        full_key = self._key(key)
        _s3_client(self.region).put_object(
            Bucket=self.bucket,
            Key=full_key,
            Body=data,
            ContentType=mimetypes.guess_file_type(key)[0] or "application/octet-stream",
            ServerSideEncryption="AES256",
            CacheControl="public, max-age=300",
            # File mới có UUID; không ghi đè object hiện hữu khi có xung đột.
            IfNoneMatch="*",
        )
        return self.url(key)

    def url(self, key: str) -> str:
        return f"{self.cdn_url}/{quote(self._key(key), safe='/')}"

    def read(self, key: str) -> bytes:
        full_key = self._key(key)
        response = _s3_client(self.region).get_object(Bucket=self.bucket, Key=full_key)
        body = response["Body"]
        try:
            return body.read()
        finally:
            body.close()

    def delete(self, key: str) -> None:
        full_key = self._key(key)
        _s3_client(self.region).delete_object(Bucket=self.bucket, Key=full_key)

    def download(self, key: str, destination: Path, max_bytes: int) -> None:
        response = _s3_client(self.region).get_object(
            Bucket=self.bucket, Key=self._key(key)
        )
        body = response["Body"]
        try:
            if response.get("ContentLength", 0) > max_bytes:
                raise ValueError("Media exceeds processing limit")
            _copy_chunks(body.iter_chunks(1024 * 1024), destination, max_bytes)
        finally:
            body.close()


def _copy_chunks(chunks, destination: Path, max_bytes: int) -> None:
    total = 0
    with destination.open("wb") as output:
        for chunk in chunks:
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("Media exceeds processing limit")
            output.write(chunk)


def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "supabase":
        return SupabaseStorage(s.supabase_url, s.supabase_service_key, s.storage_bucket)
    if s.storage_backend == "s3":
        return S3Storage(s.s3_bucket, s.s3_region, s.s3_cdn_url, s.s3_key_prefix)
    if s.storage_backend == "local":
        return LocalStorage(s.media_root)
    raise ValueError("Storage backend không được hỗ trợ")
