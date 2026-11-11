"""Member upload budgets, strict file limits and race-safe abandoned upload cleanup."""

import asyncio
import os
import threading
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models.enums import UserRole
from app.models.media import Media
from app.services import member_uploads
from app.services.member_upload_cleanup import cleanup_expired
from app.services.storage import get_storage
from tests.test_cms_api import auth
from tests.test_community_api import token_for
from tests.test_media_api import mp4_bytes, png_bytes


async def test_concurrent_janitors_do_not_delete_the_same_upload_twice(
    make_media, monkeypatch
):
    await make_media(upload_expires_at=datetime.now(UTC) - timedelta(hours=1))
    started, release = threading.Event(), threading.Event()

    class SlowStorage:
        def delete(self, key):
            started.set()
            assert release.wait(5)

    monkeypatch.setattr(
        "app.services.member_upload_cleanup.get_storage", lambda: SlowStorage()
    )

    async def first_pass():
        async with SessionLocal() as first:
            return await cleanup_expired(first, apply=True)

    first = asyncio.create_task(first_pass())
    try:
        assert await asyncio.to_thread(started.wait, 3)
        async with SessionLocal() as second:
            assert (await cleanup_expired(second, apply=True))["candidates"] == 0
    finally:
        release.set()
    assert (await first)["deleted"] == 1


async def test_upload_body_timeout_releases_slot_before_storage(
    client, make_user, monkeypatch
):
    async def stalled_body(*args, **kwargs):
        await asyncio.sleep(60)

    _, token = await token_for(client, make_user, UserRole.member)
    monkeypatch.setattr(get_settings(), "member_upload_timeout_seconds", 0.01)
    monkeypatch.setattr("app.routers.community.parse_upload", stalled_body)
    response = await client.post(
        "/api/community/uploads", content=b"fixture", headers=auth(token)
    )
    assert response.status_code == 408
    assert not any(member_uploads._slots.values())


@pytest.mark.parametrize("pending", [False, True])
async def test_expired_upload_cannot_be_attached_or_reprocessed(
    client, make_media, make_user, track_content, monkeypatch, pending
):
    from tests.test_cms_api import token_for as cms_token

    token = await cms_token(client, make_user, UserRole.admin)
    media = await make_media(
        upload_expires_at=datetime.now(UTC) - timedelta(minutes=1),
        cleanup_pending=pending,
    )
    response = await client.post(
        "/admin/content",
        json={
            "type": "gallery",
            "title": "Expired review fixture",
            "media": [{"media_id": media.id}],
        },
        headers=auth(token),
    )
    assert response.status_code == 422, response.text
    monkeypatch.setattr(get_settings(), "media_processing_enabled", True)
    response = await client.post(
        f"/admin/media/{media.id}/process", headers=auth(token)
    )
    assert response.status_code == 410


@pytest.mark.skipif(
    not os.environ.get("REDIS_URL"),
    reason="Shared quota Lua is tested with isolated CI Redis",
)
async def test_real_redis_byte_budgets_and_slots_are_atomic(monkeypatch):
    from urllib.parse import urlsplit

    from redis.asyncio import Redis

    settings = get_settings()
    parsed = urlsplit(settings.redis_url)
    assert (
        parsed.hostname in {"localhost", "127.0.0.1", "redis"} and parsed.path == "/15"
    )
    redis = Redis.from_url(settings.redis_url, socket_timeout=2)
    tag = uuid4().hex
    original_scopes = member_uploads._scopes
    original_eval = member_uploads._eval
    seen = set()

    async def tracked(script, keys, args):
        seen.update(keys)
        return await original_eval(script, keys, args)

    monkeypatch.setattr(settings, "environment", "prod")
    monkeypatch.setattr(settings, "member_upload_user_daily_bytes", 11)
    monkeypatch.setattr(settings, "member_upload_ip_daily_bytes", 20)
    monkeypatch.setattr(member_uploads, "_get_redis", lambda: redis)
    monkeypatch.setattr(
        member_uploads,
        "_scopes",
        lambda uid, ip: tuple(tag + ":" + key for key in original_scopes(uid, ip)),
    )
    monkeypatch.setattr(member_uploads, "_eval", tracked)
    try:
        results = await asyncio.gather(
            *(member_uploads.charge(1, "shared-ip", 1) for _ in range(20)),
            return_exceptions=True,
        )
        assert results.count(None) == 11
        assert all(
            isinstance(r, HTTPException) and r.status_code == 429
            for r in results
            if r is not None
        )
        counters = [key for key in seen if ":bytes:" in key]
        assert await redis.mget(counters) == [b"11"] * 3
        assert all(
            ttl > 0
            for ttl in await asyncio.gather(*(redis.ttl(key) for key in counters))
        )
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(member_uploads.slot(1, "same-ip"))
            await stack.enter_async_context(member_uploads.slot(1, "same-ip"))
            with pytest.raises(HTTPException):
                async with member_uploads.slot(1, "other-ip"):
                    pytest.fail("Per-user slot limit bypassed")
            await stack.enter_async_context(member_uploads.slot(2, "same-ip"))
            with pytest.raises(HTTPException):
                async with member_uploads.slot(3, "same-ip"):
                    pytest.fail("Per-IP slot limit bypassed")
            await stack.enter_async_context(member_uploads.slot(3, "other-ip"))
            with pytest.raises(HTTPException):
                async with member_uploads.slot(4, "third-ip"):
                    pytest.fail("Global slot limit bypassed")
        for key in seen:
            if ":active:" in key:
                assert await redis.zcard(key) == 0
    finally:
        if seen:
            await redis.delete(*seen)
        await redis.aclose()


async def test_cleanup_skips_upload_locked_by_attachment(db, make_media):
    media = await make_media(upload_expires_at=datetime.now(UTC) - timedelta(hours=1))
    await db.scalar(
        select(Media)
        .where(Media.id == media.id)
        .with_for_update(read=True, key_share=True)
    )
    async with SessionLocal() as janitor:
        result = await cleanup_expired(janitor, apply=True)
    assert result["candidates"] == 0
    await db.rollback()


@pytest.mark.parametrize("extra,status", [(-1, 201), (0, 201), (1, 413)])
async def test_member_video_limit_excludes_multipart_overhead(
    client, make_user, track_media, monkeypatch, extra, status
):
    _, token = await token_for(client, make_user, UserRole.member)
    monkeypatch.setattr(get_settings(), "max_post_video_size", 1024)
    data = mp4_bytes()
    response = await client.post(
        "/api/community/uploads",
        files={
            "file": ("clip.mp4", data + b"\0" * (1024 + extra - len(data)), "video/mp4")
        },
        headers=auth(token),
    )
    assert response.status_code == status, response.text
    if status == 201:
        track_media.append(response.json()["id"])


async def test_member_budget_is_checked_before_storage(
    client, make_user, db, monkeypatch
):
    user, token = await token_for(client, make_user, UserRole.member)
    monkeypatch.setattr(get_settings(), "member_upload_user_daily_bytes", 1)
    response = await client.post(
        "/api/community/uploads",
        files={"file": ("photo.png", png_bytes(), "image/png")},
        headers=auth(token),
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert not (
        await db.scalars(select(Media).where(Media.uploaded_by == user.id))
    ).all()


@pytest.mark.parametrize("scope", ["user", "ip", "global"])
async def test_byte_budgets_reject_atomically_without_charging_other_scopes(
    monkeypatch, scope
):
    settings = get_settings()
    for name in ("user", "ip", "global"):
        monkeypatch.setattr(
            settings, f"member_upload_{name}_daily_bytes", 10 if name == scope else 100
        )
    await member_uploads.charge(1, "127.0.0.1", 10)
    before = dict(member_uploads._bytes)
    with pytest.raises(HTTPException) as error:
        await member_uploads.charge(1, "127.0.0.1", 1)
    assert error.value.status_code == 429
    assert member_uploads._bytes == before
    assert all("127.0.0.1" not in key for key in before)


async def test_different_users_share_ip_byte_budget(monkeypatch):
    monkeypatch.setattr(get_settings(), "member_upload_ip_daily_bytes", 10)
    await member_uploads.charge(1, "same-ip", 10)
    with pytest.raises(HTTPException) as error:
        await member_uploads.charge(2, "same-ip", 1)
    assert error.value.status_code == 429
    await member_uploads.charge(2, "another-ip", 1)


async def test_concurrent_uploads_are_bounded_and_release_on_error():
    async with member_uploads.slot(1, "same-ip"), member_uploads.slot(1, "same-ip"):
        with pytest.raises(HTTPException):
            async with member_uploads.slot(1, "other-ip"):
                pytest.fail("Third upload for the same user was admitted")
    with pytest.raises(RuntimeError):
        async with member_uploads.slot(1, "same-ip"):
            raise RuntimeError("release")
    async with member_uploads.slot(1, "same-ip"), member_uploads.slot(1, "same-ip"):
        pass


async def test_production_quota_backend_failure_rejects_uploads(monkeypatch):
    class Unavailable:
        async def eval(self, *args):
            raise OSError("no redis")

    monkeypatch.setattr(get_settings(), "environment", "prod")
    monkeypatch.setattr(member_uploads, "_get_redis", lambda: Unavailable())
    with pytest.raises(HTTPException) as error:
        await member_uploads.charge(1, "ip", 1)
    assert error.value.status_code == 503
    with pytest.raises(HTTPException) as error:
        async with member_uploads.slot(1, "ip"):
            pytest.fail("Upload admitted without a shared limiter")
    assert error.value.status_code == 503


async def test_cleanup_only_new_expired_unattached_uploads(
    db, make_media, make_content, link_media, tmp_path, monkeypatch
):
    monkeypatch.setattr(get_settings(), "media_root", str(tmp_path))
    now = datetime.now(UTC)
    expired = await make_media(upload_expires_at=now - timedelta(hours=1))
    existing = await make_media()  # Every pre-migration media keeps a NULL expiry.
    fresh = await make_media(upload_expires_at=now + timedelta(hours=1))
    attached = await make_media(upload_expires_at=now - timedelta(hours=1))
    active = await make_media(
        upload_expires_at=now - timedelta(hours=1),
        processing_lease_until=now + timedelta(minutes=1),
    )
    content = await make_content()
    await link_media(content, attached)
    storage = get_storage()
    for media in (expired, existing, fresh, attached, active):
        storage.save(media.storage_key, b"fixture")
    preview = await cleanup_expired(db)
    assert preview == {"candidates": 1, "deleted": 0, "failed": 0}
    assert (tmp_path / expired.storage_key).exists()
    result = await cleanup_expired(db, apply=True)
    assert result == {"candidates": 1, "deleted": 1, "failed": 0}
    assert not (tmp_path / expired.storage_key).exists()
    assert await db.get(Media, expired.id) is None
    for media in (existing, fresh, attached, active):
        assert (tmp_path / media.storage_key).exists()


async def test_cleanup_keeps_tombstone_and_retries_storage_failures(
    db, make_media, monkeypatch
):
    media = await make_media(upload_expires_at=datetime.now(UTC) - timedelta(hours=1))

    class FailingStorage:
        fail = True

        def delete(self, key):
            if self.fail:
                raise OSError("storage unavailable")

    storage = FailingStorage()
    monkeypatch.setattr(
        "app.services.member_upload_cleanup.get_storage", lambda: storage
    )
    result = await cleanup_expired(db, apply=True)
    assert result == {"candidates": 1, "deleted": 0, "failed": 1}
    await db.refresh(media)
    assert media.cleanup_pending
    storage.fail = False
    assert (await cleanup_expired(db, apply=True))["deleted"] == 1


async def test_attaching_upload_cancels_expiry_atomically(
    client, db, make_user, track_media, track_content
):
    _, token = await token_for(client, make_user, UserRole.member)
    response = await client.post(
        "/api/community/uploads",
        files={"file": ("photo.png", png_bytes(), "image/png")},
        headers=auth(token),
    )
    assert response.status_code == 201
    media_id = response.json()["id"]
    track_media.append(media_id)
    media = await db.get(Media, media_id)
    assert media.upload_expires_at is not None
    response = await client.post(
        "/api/community/posts",
        json={"summary": "Review fixture post", "media_ids": [media_id]},
        headers=auth(token),
    )
    assert response.status_code == 201, response.text
    from app.models.content import Content
    from app.models.media import ContentMedia

    post_id = await db.scalar(
        select(ContentMedia.content_id).where(ContentMedia.media_id == media_id)
    )
    track_content.append(post_id)
    await db.refresh(media)
    assert media.upload_expires_at is None
    post = await db.get(Content, post_id)
    assert post.status.value == "draft"
