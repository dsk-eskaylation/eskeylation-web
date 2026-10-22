"""Media pipeline regressions using generated files and isolated Postgres only."""

import asyncio
import io
import threading
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models.enums import UserRole
from app.models.media import Media
from app.services import media_jobs
from app.services.catalog_revision import database_revision
from app.services.media_processing import ProcessingError, process_file
from app.services.storage import LocalStorage
from tests.test_cms_api import auth, token_for


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "media_root", str(tmp_path))
    return LocalStorage(str(tmp_path))


def image_bytes(size=(1800, 900), exif=None):
    buffer = io.BytesIO()
    Image.new("RGB", size, "#773344").save(
        buffer, "JPEG", **({"exif": exif} if exif else {})
    )
    return buffer.getvalue()


def test_image_variants_keep_original_and_never_upscale(storage):
    original = image_bytes()
    storage.save("original.jpg", original)
    result = process_file(storage, 42, "token", "original.jpg", "image/jpeg")
    images = result["variants"]["images"]
    assert [image["width"] for image in images] == [480, 960, 1600, 1800]
    assert storage.read("original.jpg") == original
    for image in images:
        with Image.open(io.BytesIO(storage.read(image["key"]))) as variant:
            assert variant.format == "WEBP"
            assert variant.size == (image["width"], image["height"])
    storage.save("small.jpg", image_bytes((37, 19)))
    small = process_file(storage, 43, "token", "small.jpg", "image/jpeg")
    assert len(small["variants"]["images"]) == 1
    assert small["variants"]["images"][0]["width"] == 37


def test_image_orientation_and_oversized_original(storage):
    exif = Image.Exif()
    exif[274] = 6
    storage.save("rotated.jpg", image_bytes((100, 50), exif))
    result = process_file(storage, 1, "token", "rotated.jpg", "image/jpeg")
    assert (result["width"], result["height"]) == (50, 100)
    storage.save("huge.jpg", image_bytes((4001, 4000)))
    with pytest.raises(ProcessingError, match="image_too_large"):
        process_file(storage, 2, "token", "huge.jpg", "image/jpeg")
    assert storage.read("huge.jpg")


def test_storage_download_is_bounded(storage, tmp_path):
    storage.save("file", b"a" * 1025)
    with pytest.raises(ValueError):
        storage.download("file", tmp_path / "download", 1024)
    assert (tmp_path / "download").stat().st_size == 0


async def test_lease_recovers_and_old_token_cannot_process(db, make_media, storage):
    media = await make_media()
    storage.save(media.storage_key, image_bytes((40, 20)))
    media_jobs.queue(media)
    await db.commit()
    first = (await media_jobs.reserve(db))[0]
    media.processing_lease_until = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()
    second = (await media_jobs.reserve(db))[0]
    assert first[1] != second[1]
    await media_jobs.process(db, *first)
    await db.refresh(media)
    assert media.processing_attempts == 0
    await media_jobs.process(db, *second)
    await db.refresh(media)
    assert media.processing_status == "ready"
    assert media.processing_attempts == 1
    before = sorted(storage.root.rglob("*.webp"))
    await media_jobs.process(db, *second)
    assert sorted(storage.root.rglob("*.webp")) == before


async def test_failed_jobs_retry_three_times_with_safe_errors(
    db, make_media, storage, monkeypatch
):
    media = await make_media()
    media_jobs.queue(media)
    await db.commit()

    def fail(*args):
        raise RuntimeError("secret-credential-never-expose")

    monkeypatch.setattr(media_jobs, "process_file", fail)
    for attempt in range(1, 4):
        await media_jobs.process(db, *(await media_jobs.reserve(db))[0])
        await db.refresh(media)
        assert media.processing_attempts == attempt
        assert media.processing_error_code == "processing_failed"
        assert media.processing_status == ("failed" if attempt == 3 else "pending")
        if attempt < 3:
            media.processing_next_at = datetime.now(UTC) - timedelta(seconds=1)
            await db.commit()
    assert await media_jobs.reserve(db) == []


async def test_delete_during_processing_does_not_resurrect_or_leave_derivatives(
    db, make_media, storage, monkeypatch
):
    media = await make_media()
    media_jobs.queue(media)
    await db.commit()
    job = (await media_jobs.reserve(db))[0]
    started, release = threading.Event(), threading.Event()
    key = f"derived/{media.id}/{job[1]}/image-40.webp"

    def transform(*args):
        started.set()
        assert release.wait(10)
        storage.save(key, b"fake derivative")
        return {"variants": {"images": [{"key": key, "width": 40}]}}

    monkeypatch.setattr(media_jobs, "process_file", transform)
    async with SessionLocal() as worker:
        task = asyncio.create_task(media_jobs.process(worker, *job))
        try:
            assert await asyncio.to_thread(started.wait, 10)
            await db.delete(media)
            await db.commit()
        finally:
            release.set()
        await task
    assert await db.scalar(select(Media.id).where(Media.id == job[0])) is None
    assert not (storage.root / key).exists()


async def test_completion_updates_public_revision_and_preserves_original(
    db, make_content, make_media, link_media, storage, client
):
    content = await make_content()
    media = await make_media()
    storage.save(media.storage_key, image_bytes((1000, 500)))
    await link_media(content, media)
    before = await database_revision(db)
    media_jobs.queue(media)
    await db.commit()
    await media_jobs.process(db, *(await media_jobs.reserve(db))[0])
    after = await database_revision(db)
    assert before != after
    output = (await client.get(f"/api/music/{content.slug}")).json()["media"][0]
    assert output["original_url"].endswith(media.storage_key)
    assert "480w" in output["srcset"]
    assert "960w" in output["srcset"]
    assert "processing_status" not in output


async def test_admin_jobs_retry_auth_and_duplicate_protection(
    client, make_user, make_media, db, storage, monkeypatch
):
    assert (await client.get("/admin/media/jobs")).status_code == 401
    author = await token_for(client, make_user, UserRole.author)
    assert (
        await client.get("/admin/media/jobs", headers=auth(author))
    ).status_code == 403
    admin = await token_for(client, make_user, UserRole.admin)
    monkeypatch.setattr(get_settings(), "media_processing_enabled", True)
    media = await make_media()
    response = await client.post(
        f"/admin/media/{media.id}/process", headers=auth(admin)
    )
    assert response.status_code == 202
    assert response.json()["processing_status"] == "pending"
    assert (
        await client.post(f"/admin/media/{media.id}/process", headers=auth(admin))
    ).status_code == 409
    response = await client.get("/admin/media/jobs", headers=auth(admin))
    assert response.status_code == 200
    assert response.json()["counts"]["pending"] == 1
    assert response.json()["enabled"] is True


async def test_upload_records_job_without_contacting_broker(
    client, make_user, track_media, storage, monkeypatch
):
    from app.workers.tasks import process_media

    monkeypatch.setattr(get_settings(), "media_processing_enabled", True)

    def broker_is_down(*args, **kwargs):
        raise AssertionError("HTTP upload must never publish to Redis")

    monkeypatch.setattr(process_media, "apply_async", broker_is_down)
    admin = await token_for(client, make_user, UserRole.admin)
    response = await client.post(
        "/admin/media",
        files={"file": ("fake.jpg", image_bytes((40, 20)), "image/jpeg")},
        headers=auth(admin),
    )
    assert response.status_code == 201
    data = response.json()
    track_media.append(data["id"])
    assert data["processing_status"] == "pending"
    assert data["processing_attempts"] == 0


async def test_delete_cleans_original_and_only_owned_derivatives(
    db, make_media, storage
):
    from app.services.media import delete_media

    media = await make_media()
    key = f"derived/{media.id}/token/image-40.webp"
    unrelated = "derived/999999/token/image-40.webp"
    media.variants = {"images": [{"key": key}, {"key": unrelated}]}
    await db.commit()
    for filename in (media.storage_key, key, unrelated):
        storage.save(filename, b"fake file")
    await delete_media(db, media)
    assert not (storage.root / media.storage_key).exists()
    assert not (storage.root / key).exists()
    assert (storage.root / unrelated).exists()
