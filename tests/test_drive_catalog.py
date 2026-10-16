"""Public website dùng Drive: không DB, không tải/copy media, không lộ khóa."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.models.enums import ContentType
from app.routers import public
from app.services.drive_catalog import DriveCatalog, file_to_content
from app.services.drive_metadata import FOLDER_MIME


def row(file_id="file_123456789", **kwargs):
    return {
        "id": file_id,
        "name": "Bình tĩnh - DSK.mp3",
        "mimeType": "audio/mpeg",
        "thumbnailLink": "https://lh3.googleusercontent.com/test=s220",
        **kwargs,
    }


def test_file_uses_native_media_and_stable_opaque_id():
    item = file_to_content(row(resourceKey="key-1"), ["Nhạc & MV"])
    assert item.body == {
        "source": "google_drive",
        "artist": "DSK",
        "audio_url": f"/api/library/{item.id}/stream",
    }
    assert item.published_at is None
    assert item.media[0].preview_url is None
    assert item.media[0].stream_url == item.body["audio_url"]
    assert "file_123456789" not in item.model_dump_json()
    assert "key-1" not in item.model_dump_json()
    assert item._drive["id"] == "file_123456789"
    assert -(2**53) < item.id < 0
    assert item.id == file_to_content(row(name="Đổi tên"), ["Nhạc & MV"]).id
    assert "supabase" not in item.model_dump_json()


def test_unknown_thumbnail_host_is_not_rendered():
    item = file_to_content(row(thumbnailLink="https://evil.test/a"), ["Nhạc & MV"])
    assert item.media[0].url == ""
    assert item.media[0].preview_url is None
    assert file_to_content(row(mimeType="application/zip"), ["Nhạc & MV"]) is None


def test_modified_files_have_versioned_urls_and_heif_has_browser_safe_full_view():
    before = file_to_content(row(modifiedTime="2026-10-15"), ["Nhạc & MV"])
    after = file_to_content(row(modifiedTime="2026-10-16"), ["Nhạc & MV"])
    assert before.id == after.id
    assert before.body["audio_url"] != after.body["audio_url"]
    image = file_to_content(
        row(mimeType="image/heif", modifiedTime="2026-10-16"), ["Cộng đồng"]
    )
    assert "/image?w=1920&v=" in image.media[0].original_url
    assert "&v=" in image.media[0].srcset


async def test_scan_handles_pages_and_only_requests_metadata():
    requests = []

    def handler(request):
        requests.append(request)
        assert "alt" not in request.url.params
        if request.url.path.endswith("/root_123456789"):
            data = {"mimeType": FOLDER_MIME}
        elif "child_123456789" in request.url.params.get("q", ""):
            data = {"files": [row(), row("file_987654321", name="ABC - DSK")]}
        elif request.url.params.get("pageToken"):
            data = {"files": [row("file_987654321")]}
        else:
            data = {
                "nextPageToken": "next",
                "files": [
                    {
                        "id": "child_123456789",
                        "name": "Nhạc & MV",
                        "mimeType": FOLDER_MIME,
                    }
                ],
            }
        return httpx.Response(200, json=data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await DriveCatalog()._scan(client, "root_123456789")
    assert len(items) == 2
    assert any(r.url.params.get("pageToken") == "next" for r in requests)
    assert len(requests) == 4


async def test_cache_shares_concurrent_fetches(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_drive_api_key", "test-secret")
    catalog = DriveCatalog()
    catalog._scan = AsyncMock(return_value=[])
    await asyncio.gather(catalog.items(), catalog.items(), catalog.items())
    catalog._scan.assert_awaited_once()


async def test_changed_folder_refreshes_cache(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "google_drive_api_key", "test-secret")
    catalog = DriveCatalog()
    catalog._scan = AsyncMock(return_value=[])
    await catalog.items()
    monkeypatch.setattr(settings, "google_drive_folder_id", "other_123456789")
    await catalog.items()
    assert catalog._scan.await_count == 2


async def test_revision_changes_after_delete_and_modify_without_leaking_drive_id(
    monkeypatch,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "google_drive_api_key", "test-secret")
    monkeypatch.setattr(settings, "drive_catalog_cache_seconds", 0)
    catalog = DriveCatalog()
    first = file_to_content(row(), ["Nhạc & MV"])
    other = file_to_content(row("file_987654321"), ["Nhạc & MV"])
    catalog._scan = AsyncMock(side_effect=[[first, other], [first], [first], []])
    await catalog.items()
    original = catalog.revision
    await catalog.items()
    deleted = catalog.revision
    assert deleted != original and len(deleted) == 32
    first._drive["modifiedTime"] = "2026-10-16T15:00:00Z"
    await catalog.items()
    assert catalog.revision != deleted
    assert "file_" not in catalog.revision and "test-secret" not in catalog.revision
    await catalog.items()
    assert catalog._by_id == {}


async def test_revision_api_no_store_no_database(client, drive_source):
    drive_source.revision = "opaque-revision"
    response = await client.get("/api/catalog")
    assert response.status_code == 200
    assert response.json() == {"revision": "opaque-revision"}
    assert response.headers["cache-control"] == "no-store"


async def test_deleted_image_disappears_when_shared_catalog_cache_expires(monkeypatch):
    from app.services import drive_catalog

    monkeypatch.setattr(get_settings(), "google_drive_api_key", "test-secret")
    monkeypatch.setattr(get_settings(), "drive_catalog_cache_seconds", 15)
    now = 0.0
    monkeypatch.setattr(drive_catalog, "monotonic", lambda: now)
    catalog = DriveCatalog()
    image = file_to_content(row(mimeType="image/jpeg"), ["Cộng đồng"])
    catalog._scan = AsyncMock(side_effect=[[image], []])
    assert (await catalog.page(ContentType.community, 1, 30, None)).total == 1
    now = 14.0
    assert (await catalog.page(ContentType.community, 1, 30, None)).total == 1
    now = 15.0
    assert (await catalog.page(ContentType.community, 1, 30, None)).total == 0
    assert await catalog.get(image.id) is None


@pytest.fixture
def drive_source(monkeypatch):
    monkeypatch.setattr(get_settings(), "public_content_source", "drive")
    catalog = DriveCatalog()
    catalog.items = AsyncMock(
        return_value=[
            file_to_content(row(), ["Nhạc & MV"]),
            file_to_content(row("file_987654321", name="ABC - Guest"), ["Nhạc & MV"]),
            file_to_content(
                row("file_111111111", name="Ảnh", mimeType="image/jpeg"), ["Ảnh"]
            ),
            file_to_content(
                row("file_video_123", name="Live.mp4", mimeType="video/mp4"), ["Video"]
            ),
        ]
    )
    monkeypatch.setattr(public, "catalog", catalog)

    def forbidden_db():
        raise AssertionError("Drive website must not request a database session")

    monkeypatch.setattr(public, "get_session", forbidden_db)
    return catalog


async def test_public_search_pagination_and_detail_without_database(
    client, drive_source
):
    response = await client.get("/api/music", params={"q": "binh tinh", "page_size": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Bình tĩnh"
    slug = data["items"][0]["slug"]
    assert "status" not in data["items"][0]
    assert "author_id" not in data["items"][0]
    assert (await client.get(f"/api/music/{slug}")).status_code == 200
    assert (await client.get(f"/api/photos/{slug}")).status_code == 404
    assert (await client.get("/api/music", params={"artist": "Guest"})).json()[
        "total"
    ] == 1
    assert (await client.get("/api/photos")).json()["total"] == 1
    assert (await client.get("/api/community")).json()["total"] == 0
    assert (await client.get("/api/homepage")).status_code == 200
    video = (await client.get("/api/video")).json()
    assert video["total"] == 1
    assert (
        await client.get(f"/api/video/{video['items'][0]['slug']}")
    ).status_code == 200
    assert "drive.google.com" not in response.headers["content-security-policy"]


async def test_drive_failure_does_not_fall_back_to_database(client, drive_source):
    drive_source.items.side_effect = HTTPException(503, "Drive unavailable")
    response = await client.get("/api/music")
    assert response.status_code == 503
    assert "secret" not in response.text


async def test_content_check_separate_from_full_database_readiness(
    client, drive_source, monkeypatch
):
    from app import main

    monkeypatch.setattr(main, "catalog", drive_source)

    def forbidden_connect():
        raise AssertionError("Drive readiness must not connect to database")

    monkeypatch.setattr(main, "engine", SimpleNamespace(connect=forbidden_connect))
    response = await client.get("/health/content")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert (await client.get("/health/ready")).status_code == 503


async def test_cache_failure_does_not_expose_credentials(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_drive_api_key", "test-secret")
    catalog = DriveCatalog()
    catalog._scan = AsyncMock(side_effect=ValueError("test-secret"))
    with pytest.raises(HTTPException) as error:
        await catalog.items()
    assert error.value.status_code == 503
    assert "test-secret" not in error.value.detail


async def test_filters_and_pages(drive_source):
    page = await drive_source.page(ContentType.music, 2, 1, None)
    assert page.total == 2
    assert len(page.items) == 1
    assert (
        await drive_source.page(
            ContentType.music, 1, 10, None, {"category": "unassigned"}
        )
    ).total == 0


async def test_thumbnail_reads_from_google_without_storage(monkeypatch):
    catalog = DriveCatalog()
    catalog.items = AsyncMock(return_value=[])
    catalog._thumbnails = {"file_123456789": "https://lh3.googleusercontent.com/a"}
    original_client = httpx.AsyncClient
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200, content=b"image-data", headers={"content-type": "image/jpeg"}
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original_client(transport=httpx.MockTransport(handler), **kw),
    )
    response = await catalog.thumbnail("file_123456789")
    assert response.body == b"image-data"
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "public, max-age=300"
    assert len(requests) == 1
    with pytest.raises(HTTPException) as error:
        await catalog.thumbnail("unknown_file_id")
    assert error.value.status_code == 404
    assert len(requests) == 1


async def test_thumbnail_rejects_html(monkeypatch):
    catalog = DriveCatalog()
    catalog.items = AsyncMock(return_value=[])
    catalog._thumbnails = {"file_123456789": "https://lh3.googleusercontent.com/a"}
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original_client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, text="<html>not an image</html>")
            ),
            **kw,
        ),
    )
    with pytest.raises(HTTPException) as error:
        await catalog.thumbnail("file_123456789")
    assert error.value.status_code == 503
