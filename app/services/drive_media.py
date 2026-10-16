"""Media cùng origin: catalog allowlist, Range và ảnh WebP có cache giới hạn."""

import asyncio
import hashlib
import io
import json
import logging
import re
from collections import OrderedDict
from time import monotonic
from urllib.parse import urlparse, urlunparse
from weakref import WeakValueDictionary

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.schemas.public import ContentOut
from app.services import drive_http
from app.services.drive_catalog import catalog, google_thumbnail

_images: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
_image_bytes = 0
_image_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
_image_slots = asyncio.Semaphore(4)
_streams = asyncio.Semaphore(get_settings().drive_stream_concurrency)
_RANGE = re.compile(r"bytes=(\d{0,18})-(\d{0,18})")
_CONTENT_RANGE = re.compile(r"bytes \d+-\d+/\d+")
logger = logging.getLogger(__name__)
register_heif_opener(thumbnails=False, decode_threads=2)


def _log_failure(
    request: Request,
    content_id: int,
    started: float,
    error: Exception,
    upstream_status: int | None,
    phase: str,
) -> None:
    logger.warning(
        json.dumps(
            {
                "event": "media_upstream_failed",
                "asset_id": content_id,
                "request_id": getattr(request.state, "request_id", ""),
                "upstream_status": upstream_status,
                "error_type": type(error).__name__,
                "duration_ms": round((monotonic() - started) * 1000),
                "phase": phase,
            }
        )
    )


async def asset(content_id: int) -> ContentOut:
    if get_settings().public_content_source != "drive":
        raise HTTPException(404, "Không tìm thấy tư liệu")
    content = await catalog.get(content_id)
    if content is None or not content._drive.get("id"):
        raise HTTPException(404, "Không tìm thấy tư liệu")
    return content


def etag(content: ContentOut, variant: str = "original") -> str:
    version = (
        f"{content.id}:{content._drive.get('modifiedTime', '')}:"
        f"{content._drive.get('size', '')}:{variant}"
    )
    return '"' + hashlib.sha256(version.encode()).hexdigest()[:32] + '"'


def _size(content: ContentOut) -> int:
    value = str(content._drive.get("size", "0"))
    return int(value) if value.isdigit() else 0


def _range(value: str, size: int) -> str:
    match = _RANGE.fullmatch(value.strip())
    if match is None or not any(match.groups()):
        raise HTTPException(
            416,
            "Khoảng dữ liệu không hợp lệ",
            headers={"Content-Range": f"bytes */{size}"},
        )
    start, end = match.groups()
    if (
        (start and end and int(end) < int(start))
        or (not start and int(end) == 0)
        or (size and start and int(start) >= size)
    ):
        raise HTTPException(
            416,
            "Khoảng dữ liệu không hợp lệ",
            headers={"Content-Range": f"bytes */{size}"},
        )
    return f"bytes={start}-{end}"


def _upstream_error(status: int) -> HTTPException:
    if status == 404:
        return HTTPException(404, "Tư liệu không còn khả dụng")
    if status == 403:
        # Google can reject anonymous downloads or throttle traffic with 403.
        # Metadata may still be readable: this does not prove the file was deleted.
        return HTTPException(
            503,
            "Kho tư liệu đang tạm từ chối tải. Vui lòng thử lại sau.",
            headers={"Retry-After": "60"},
        )
    return HTTPException(
        503, "Tạm thời chưa tải được tư liệu", headers={"Retry-After": "5"}
    )


async def stream(content_id: int, request: Request, *, head: bool = False) -> Response:
    started = monotonic()
    content = await asset(content_id)
    size = _size(content)
    tag = etag(content)
    mime = content.media[0].mime_type
    headers = {
        "Accept-Ranges": "bytes",
        "ETag": tag,
        "Cache-Control": "public, max-age=300",
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
        "X-Accel-Buffering": "no",
    }
    if head:
        if size:
            headers["Content-Length"] = str(size)
        return Response(headers=headers, media_type=mime)
    requested_range = request.headers.get("range")
    if request.headers.get("if-range") not in (None, tag):
        requested_range = None
    if not requested_range and request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers=headers)
    outgoing = await drive_http.headers(
        content._drive.get("resourceKey"), content._drive["id"]
    )
    if requested_range:
        outgoing["Range"] = _range(requested_range, size)
    try:
        await asyncio.wait_for(_streams.acquire(), timeout=5)
    except TimeoutError:
        raise HTTPException(
            503, "Máy chủ đang bận, vui lòng thử lại", headers={"Retry-After": "2"}
        ) from None
    upstream = None
    released = False

    async def cleanup():
        nonlocal released
        if not released:
            released = True
            try:
                if upstream is not None:
                    await upstream.aclose()
            finally:
                _streams.release()

    try:
        client = drive_http.client()
        upstream = await client.send(
            client.build_request(
                "GET",
                f"https://www.googleapis.com/drive/v3/files/{content._drive['id']}",
                params={"alt": "media"},
                headers=outgoing,
            ),
            stream=True,
        )
        if upstream.status_code == 416:
            raise HTTPException(
                416,
                "Khoảng dữ liệu không hợp lệ",
                headers={"Content-Range": f"bytes */{size}"},
            )
        if upstream.status_code not in (200, 206):
            if upstream.status_code == 404:
                catalog.invalidate()
            raise _upstream_error(upstream.status_code)
        length = upstream.headers.get("content-length", "")
        if length.isdigit():
            headers["Content-Length"] = length
        if upstream.status_code == 206:
            content_range = upstream.headers.get("content-range", "")
            if not _CONTENT_RANGE.fullmatch(content_range):
                raise HTTPException(503, "Phản hồi dữ liệu không hợp lệ")
            headers["Content-Range"] = content_range
    except (httpx.HTTPError, HTTPException) as error:
        _log_failure(
            request,
            content_id,
            started,
            error,
            upstream.status_code if upstream is not None else None,
            "headers",
        )
        await cleanup()
        if upstream is not None and upstream.status_code not in (200, 206):
            raise
        raise HTTPException(503, "Tạm thời chưa tải được tư liệu") from None
    except BaseException:
        await cleanup()
        raise

    async def chunks():
        try:
            async for chunk in upstream.aiter_raw(128 * 1024):
                yield chunk
        except httpx.HTTPError as error:
            _log_failure(
                request, content_id, started, error, upstream.status_code, "body"
            )
            raise
        finally:
            await cleanup()

    return StreamingResponse(
        chunks(),
        status_code=upstream.status_code,
        media_type=mime,
        headers=headers,
        background=BackgroundTask(cleanup),
    )


def _cached(key: str) -> bytes | None:
    global _image_bytes
    found = _images.get(key)
    if found is None:
        return None
    expiry, data = found
    if expiry <= monotonic():
        _image_bytes -= len(data)
        del _images[key]
        return None
    _images.move_to_end(key)
    return data


def _remember(key: str, data: bytes) -> None:
    global _image_bytes
    limit = get_settings().drive_image_cache_bytes
    if len(data) > limit:
        return
    previous = _images.pop(key, None)
    if previous:
        _image_bytes -= len(previous[1])
    while _images and (_image_bytes + len(data) > limit or len(_images) >= 128):
        _, (_, old) = _images.popitem(last=False)
        _image_bytes -= len(old)
    _images[key] = (monotonic() + 300, data)
    _image_bytes += len(data)


def _resize(data: bytes, width: int) -> bytes:
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 40_000_000:
                raise HTTPException(413, "Ảnh quá lớn để tạo bản xem trước")
            image.draft("RGB", (width, width * 4))
            image = ImageOps.exif_transpose(image)
            image.thumbnail((width, width * 4), Image.Resampling.LANCZOS)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            output = io.BytesIO()
            image.save(output, format="WEBP", quality=92, method=4)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, "Định dạng ảnh chưa được hỗ trợ") from None


async def _image_bytes_from(content: ContentOut, width: int, poster: bool) -> bytes:
    if poster:
        url = google_thumbnail(content._drive.get("thumbnailLink"))
        if not url:
            raise HTTPException(404, "Không có ảnh đại diện")
        parsed = urlparse(url)
        path = re.sub(r"=s\d+(?:-[A-Za-z0-9-]+)?$", "", parsed.path)
        url = urlunparse(parsed._replace(path=f"{path}=s{max(width, 960)}"))
        outgoing = {}
        params = None
    else:
        if not content.media[0].mime_type.startswith("image/"):
            raise HTTPException(404, "Không phải tư liệu ảnh")
        url = f"https://www.googleapis.com/drive/v3/files/{content._drive['id']}"
        params = {"alt": "media"}
        outgoing = await drive_http.headers(
            content._drive.get("resourceKey"), content._drive["id"]
        )
    cap = get_settings().drive_max_image_bytes if not poster else 8 * 1024 * 1024
    try:
        async with drive_http.client().stream(
            "GET", url, params=params, headers=outgoing
        ) as response:
            if response.status_code != 200:
                if response.status_code == 404:
                    catalog.invalidate()
                raise _upstream_error(response.status_code)
            if (
                not response.headers.get("content-type", "")
                .split(";")[0]
                .startswith("image/")
            ):
                raise HTTPException(503, "Phản hồi ảnh không hợp lệ")
            buffer = bytearray()
            async for chunk in response.aiter_bytes():
                buffer.extend(chunk)
                if len(buffer) > cap:
                    raise HTTPException(413, "Ảnh vượt giới hạn xử lý")
    except httpx.HTTPError:
        raise HTTPException(503, "Tạm thời chưa tải được ảnh") from None
    return await run_in_threadpool(_resize, bytes(buffer), width)


async def image(
    content_id: int, width: int, request: Request, *, poster: bool = False
) -> Response:
    content = await asset(content_id)
    tag = etag(content, f"{'poster' if poster else 'image'}-{width}")
    headers = {"Cache-Control": "public, max-age=300", "ETag": tag}
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers=headers)
    data = _cached(tag)
    if data is None:
        lock = _image_locks.get(tag)
        if lock is None:
            lock = asyncio.Lock()
            _image_locks[tag] = lock
        async with lock:
            data = _cached(tag)
            if data is None:
                async with _image_slots:
                    data = await _image_bytes_from(content, width, poster)
                _remember(tag, data)
    return Response(data, media_type="image/webp", headers=headers)
