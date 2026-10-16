"""Danh mục public từ Drive. Chỉ đọc metadata, không dùng DB hay lưu media."""

import asyncio
import hashlib
from time import monotonic
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import HTTPException
from fastapi.responses import Response
from slugify import slugify

from app.config import get_settings
from app.models.enums import ContentType
from app.schemas.pagination import Page
from app.schemas.public import ContentOut, MediaOut
from app.services.drive_metadata import FOLDER_MIME, describe_file, drive_id


def google_thumbnail(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlparse(value)
    host = parsed.hostname or ""
    if parsed.scheme == "https" and host.endswith(".googleusercontent.com"):
        return value
    return ""


def file_to_content(file: dict, folders: list[str]) -> ContentOut | None:
    item = describe_file(file, folders)
    if not item["include"]:
        return None
    file_id = drive_id(item["file_id"])
    preview = f"https://drive.google.com/file/d/{file_id}/preview"
    if file.get("resourceKey"):
        preview += "?" + urlencode({"resourcekey": file["resourceKey"]})
    body = {"source": "google_drive", "drive_file_id": file_id}
    if item["artist"]:
        body["artist"] = item["artist"]
    # ID ổn định và nằm trong miền số nguyên an toàn của JavaScript.
    # Miền âm dành cho Drive, tránh trùng ID dương của nội dung CMS.
    content_id = -1 - int.from_bytes(
        hashlib.sha256(file_id.encode()).digest()[:6], "big"
    )
    return ContentOut(
        id=content_id,
        type=ContentType(item["type"]),
        title=item["title"],
        slug=f"{slugify(item['title'])[:160] or 'tu-lieu'}-{file_id}",
        summary=file.get("description") or None,
        body=body,
        # Thời điểm sửa file không phải ngày xuất bản; không tự gán ngày.
        published_at=None,
        media=[
            MediaOut(
                url=(
                    f"/api/drive/thumbnails/{file_id}"
                    if google_thumbnail(file.get("thumbnailLink"))
                    else ""
                ),
                preview_url=preview,
                mime_type=item["mime_type"],
                alt_text=item["title"],
                is_primary=True,
            )
        ],
    )


class DriveCatalog:
    def __init__(self) -> None:
        self._items: list[ContentOut] = []
        self._expires = 0.0
        self._source: tuple[str, str] | None = None
        self._lock = asyncio.Lock()
        self._thumbnails: dict[str, str] = {}

    async def items(self) -> list[ContentOut]:
        settings = get_settings()
        source = (settings.google_drive_folder_id, settings.google_drive_api_key)
        if self._source == source and monotonic() < self._expires:
            return self._items
        async with self._lock:
            if self._source == source and monotonic() < self._expires:
                return self._items
            if not settings.google_drive_api_key:
                raise HTTPException(503, "Chưa cấu hình kết nối Google Drive")
            try:
                root = drive_id(settings.google_drive_folder_id)
                # Chỉ API key: quyền của tài khoản OAuth không mở thêm file riêng tư.
                async with httpx.AsyncClient(
                    timeout=30,
                    headers={"X-Goog-Api-Key": settings.google_drive_api_key},
                ) as client:
                    result = await self._scan(client, root)
            except (httpx.HTTPError, ValueError, KeyError):
                # Không log URL/header chứa khóa và không fallback sang Supabase.
                raise HTTPException(
                    503, "Tạm thời không đọc được thư mục Google Drive"
                ) from None
            self._items = result
            self._source = source
            self._expires = monotonic() + max(0, settings.drive_catalog_cache_seconds)
            return self._items

    async def _scan(self, client: httpx.AsyncClient, root: str) -> list[ContentOut]:
        response = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{root}",
            params={"fields": "id,mimeType"},
        )
        response.raise_for_status()
        if response.json().get("mimeType") != FOLDER_MIME:
            raise ValueError("Nguồn Drive không phải thư mục")
        queue = [(root, [])]
        seen = set()
        files_seen = set()
        items = []
        thumbnails = {}
        while queue:
            folder, path = queue.pop(0)
            if folder in seen:
                continue
            seen.add(folder)
            token = None
            while True:
                params = {
                    "q": f"'{drive_id(folder)}' in parents and trashed = false",
                    "fields": "nextPageToken,incompleteSearch,files("
                    "id,name,mimeType,thumbnailLink,resourceKey,description)",
                    "pageSize": 1000,
                    "orderBy": "name",
                }
                if token:
                    params["pageToken"] = token
                response = await client.get(
                    "https://www.googleapis.com/drive/v3/files", params=params
                )
                response.raise_for_status()
                data = response.json()
                if data.get("incompleteSearch"):
                    raise ValueError("Drive chưa trả đầy đủ danh sách")
                for file in data.get("files", []):
                    if file["mimeType"] == FOLDER_MIME:
                        queue.append((file["id"], [*path, file["name"]]))
                    elif file["id"] not in files_seen:
                        item = file_to_content(file, path)
                        if item:
                            files_seen.add(file["id"])
                            items.append(item)
                            thumbnail = google_thumbnail(file.get("thumbnailLink"))
                            if thumbnail:
                                thumbnails[file["id"]] = thumbnail
                token = data.get("nextPageToken")
                if not token:
                    break
        self._thumbnails = thumbnails
        return sorted(items, key=lambda c: (slugify(c.title), c.slug))

    async def thumbnail(self, file_id: str) -> Response:
        await self.items()
        url = self._thumbnails.get(file_id)
        if not url:
            raise HTTPException(404, "Không có ảnh thu nhỏ")
        # Chỉ URL do Drive API trả về trong thư mục đã cấu hình; không nhận URL client.
        try:
            async with (
                httpx.AsyncClient(timeout=15) as client,
                client.stream("GET", url) as response,
            ):
                response.raise_for_status()
                mime = response.headers.get("content-type", "").split(";")[0]
                if mime not in {
                    "image/jpeg",
                    "image/png",
                    "image/webp",
                    "image/avif",
                    "image/gif",
                }:
                    raise ValueError("Thumbnail không phải ảnh")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 2 * 1024 * 1024:
                        raise ValueError("Thumbnail quá lớn")
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "Tạm thời không đọc được ảnh thu nhỏ") from None
        return Response(
            bytes(data),
            media_type=mime,
            headers={"Cache-Control": "public, max-age=300"},
        )

    async def page(
        self,
        type_: ContentType,
        page: int,
        page_size: int,
        q: str | None,
        filters: dict | None = None,
    ) -> Page[ContentOut]:
        items = [item for item in await self.items() if item.type == type_]
        if q:
            query = slugify(q, separator=" ")
            items = [
                item
                for item in items
                if query
                in slugify(
                    f"{item.title} {item.body.get('artist', '')} {item.summary or ''}",
                    separator=" ",
                )
            ]
        for key, value in (filters or {}).items():
            if value:
                items = [item for item in items if item.body.get(key) == value]
        start = (page - 1) * page_size
        return Page.create(
            items[start : start + page_size], len(items), page, page_size
        )

    async def detail(self, type_: ContentType, slug: str) -> ContentOut:
        for item in await self.items():
            if item.type == type_ and item.slug == slug:
                return item
        raise HTTPException(404, "Không tìm thấy nội dung")


catalog = DriveCatalog()
