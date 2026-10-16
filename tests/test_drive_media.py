"""Native media proxy: allowlist, ranges, privacy, high-resolution images."""

import asyncio
import io
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image

from app.config import get_settings
from app.services import drive_http, drive_media
from app.services.drive_catalog import file_to_content


@pytest.fixture
def library(monkeypatch):
    monkeypatch.setattr(get_settings(), "public_content_source", "drive")
    monkeypatch.setattr(get_settings(), "google_drive_api_key", "private-test-key")
    item = file_to_content(
        {
            "id": "file_123456789",
            "name": "Song - Artist.mp3",
            "mimeType": "audio/mpeg",
            "size": "1000",
            "modifiedTime": "2026-01-01",
        },
        ["Nhạc & MV"],
    )
    lookup = AsyncMock(
        side_effect=lambda content_id: item if content_id == item.id else None
    )
    monkeypatch.setattr(drive_media.catalog, "get", lookup)
    monkeypatch.setattr(drive_media, "_streams", asyncio.Semaphore(2))
    monkeypatch.setattr(drive_media, "_image_slots", asyncio.Semaphore(2))
    drive_media._images.clear()
    monkeypatch.setattr(drive_media, "_image_bytes", 0)
    return item


def mock_upstream(monkeypatch, handler):
    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(drive_http, "_client", upstream)


class MediaBytes(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"0123456789"


async def test_range_forwarded_without_exposing_upstream_credentials(
    client, library, monkeypatch
):
    def handler(request):
        assert request.url.host == "www.googleapis.com"
        assert request.headers["x-goog-api-key"] == "private-test-key"
        assert request.headers["range"] == "bytes=10-19"
        return httpx.Response(
            206,
            stream=MediaBytes(),
            headers={
                "content-range": "bytes 10-19/1000",
                "content-length": "10",
                "location": "https://drive.google.com/private",
                "set-cookie": "secret=yes",
                "content-type": "audio/mpeg",
            },
        )

    mock_upstream(monkeypatch, handler)
    response = await client.get(
        f"/api/library/{library.id}/stream", headers={"Range": "bytes=10-19"}
    )
    assert response.status_code == 206
    assert response.content == b"0123456789"
    assert response.headers["content-range"] == "bytes 10-19/1000"
    assert "content-encoding" not in response.headers
    assert "location" not in response.headers and "set-cookie" not in response.headers
    assert "private-test-key" not in str(response.headers)
    assert drive_media._streams._value == 2


@pytest.mark.parametrize(
    "value", ["bytes=0-1,3-4", "bytes=1000-", "bytes=-0", "bytes=9-1", "no-range"]
)
async def test_invalid_range_does_not_fetch(client, library, monkeypatch, value):
    def forbidden(request):
        raise AssertionError("invalid range must not fetch")

    mock_upstream(monkeypatch, forbidden)
    response = await client.get(
        f"/api/library/{library.id}/stream", headers={"Range": value}
    )
    assert response.status_code == 416
    assert response.headers["content-range"] == "bytes */1000"


async def test_head_etag_unknown_and_cross_site_do_not_fetch(
    client, library, monkeypatch
):
    def forbidden(request):
        raise AssertionError("request must not fetch")

    mock_upstream(monkeypatch, forbidden)
    base = f"/api/library/{library.id}/stream"
    head = await client.head(base)
    assert head.status_code == 200 and head.content == b""
    assert head.headers["content-length"] == "1000"
    assert (
        await client.get(base, headers={"If-None-Match": head.headers["etag"]})
    ).status_code == 304
    assert (await client.get("/api/library/-1/stream")).status_code == 404
    assert (
        await client.get(base, headers={"Sec-Fetch-Site": "cross-site"})
    ).status_code == 403


async def test_timeout_releases_stream_slot(client, library, monkeypatch, caplog):
    def handler(request):
        raise httpx.ReadTimeout("private upstream detail", request=request)

    mock_upstream(monkeypatch, handler)
    response = await client.get(f"/api/library/{library.id}/stream")
    assert response.status_code == 503
    assert "private" not in response.text
    assert drive_media._streams._value == 2
    import json

    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "app.services.drive_media"
    ]
    assert records[0]["request_id"] == response.headers["x-request-id"]
    assert records[0]["upstream_status"] is None
    assert "private upstream detail" not in caplog.text
    assert "private-test-key" not in caplog.text


@pytest.mark.parametrize("mime", ["text/html", "application/json"])
async def test_google_forbidden_is_temporary_not_a_deleted_file(
    client, library, monkeypatch, mime
):
    mock_upstream(
        monkeypatch,
        lambda request: httpx.Response(
            403,
            text="Google rejected automated traffic",
            headers={"content-type": mime},
        ),
    )
    response = await client.get(f"/api/library/{library.id}/stream")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "60"
    assert "private-test-key" not in response.text
    assert drive_media._streams._value == 2


async def test_deleted_file_is_still_not_found(client, library, monkeypatch):
    mock_upstream(monkeypatch, lambda request: httpx.Response(404))
    response = await client.get(f"/api/library/{library.id}/stream")
    assert response.status_code == 404
    assert drive_media._streams._value == 2


async def test_disconnected_client_closes_upstream_and_releases_slot(
    library, monkeypatch
):
    from starlette.requests import Request

    class LongMedia(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            for _ in range(10):
                yield b"a" * (128 * 1024)

        async def aclose(self):
            self.closed = True

    media = LongMedia()
    mock_upstream(monkeypatch, lambda request: httpx.Response(200, stream=media))
    response = await drive_media.stream(
        library.id, Request({"type": "http", "headers": []})
    )
    assert len(await anext(response.body_iterator)) == 128 * 1024
    assert drive_media._streams._value == 1
    await response.body_iterator.aclose()
    await response.background()
    assert media.closed
    assert drive_media._streams._value == 2


async def test_image_from_original_is_resized_cached_and_has_original_link(
    client, library, monkeypatch
):
    image = Image.new("RGB", (2400, 1600), "orange")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    library.media[0].mime_type = "image/jpeg"
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.host == "www.googleapis.com"
        assert request.url.params["alt"] == "media"
        return httpx.Response(
            200, content=buffer.getvalue(), headers={"content-type": "image/jpeg"}
        )

    mock_upstream(monkeypatch, handler)
    url = f"/api/library/{library.id}/image?w=1280"
    response = await client.get(url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert Image.open(io.BytesIO(response.content)).size == (1280, 853)
    assert (await client.get(url)).content == response.content
    assert len(requests) == 1
    assert (
        await client.get(url, headers={"If-None-Match": response.headers["etag"]})
    ).status_code == 304
    assert (
        await client.get(f"/api/library/{library.id}/image?w=777")
    ).status_code == 422
    assert len(requests) == 1


async def test_heif_is_decoded_from_original_and_served_as_browser_image(
    client, library, monkeypatch
):
    buffer = io.BytesIO()
    Image.new("RGB", (1800, 1200), "orange").save(buffer, "HEIF", quality=90)
    library.media[0].mime_type = "image/heif"
    mock_upstream(
        monkeypatch,
        lambda request: httpx.Response(
            200, content=buffer.getvalue(), headers={"content-type": "image/heif"}
        ),
    )
    response = await client.get(f"/api/library/{library.id}/image?w=1280")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert Image.open(io.BytesIO(response.content)).size == (1280, 853)
