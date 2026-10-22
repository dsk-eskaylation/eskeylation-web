"""Regressions for concurrent editing, session revocation and public data contracts."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.enums import UserRole
from app.models.media import Media
from app.services import content_admin, realtime
from app.services.sanitize import restore_plain_values, sanitize_body
from tests.test_cms_api import _create, auth, token_for


async def test_audio_query_and_plain_text_survive_public_round_trip(
    client, make_user, track_content
):
    token = await token_for(client, make_user, UserRole.admin)
    body = {
        "artist": "A & B",
        "audio_url": "https://example.com/audio.mp3?token=one&format=mp3&notit=ok",
        "lyrics": "You & I <3",
    }
    content = await _create(
        client, token, track_content, type="music", title="Fake audio", body=body
    )
    assert content["body"] == body
    assert (
        await client.post(
            f"/admin/content/{content['id']}/publish", headers=auth(token)
        )
    ).status_code == 200
    assert (await client.get(f"/api/music/{content['slug']}")).json()["body"] == body


def test_legacy_entities_and_rich_html_remain_separate():
    assert restore_plain_values({"artist": "A &amp; B"}) == {"artist": "A & B"}
    assert sanitize_body({"desc": "<b>safe</b><script>x</script>"}) == {
        "desc": "<b>safe</b>x"
    }


async def test_stale_editor_is_rejected_and_media_only_changes_advance_version(
    client, make_user, make_media, track_content
):
    token = await token_for(client, make_user, UserRole.admin)
    original = await _create(
        client, token, track_content, type="gallery", title="Fake versioned"
    )
    url = f"/admin/content/{original['id']}"
    image = await make_media()
    response = await client.patch(
        url,
        headers=auth(token),
        json={
            "media": [{"media_id": image.id}],
            "expected_updated_at": original["updated_at"],
        },
    )
    assert response.status_code == 200
    assert response.json()["updated_at"] != original["updated_at"]
    stale = await client.patch(
        url,
        headers=auth(token),
        json={
            "title": "Must not overwrite",
            "expected_updated_at": original["updated_at"],
        },
    )
    assert stale.status_code == 409
    assert (await client.get(url, headers=auth(token))).json()["title"] == original[
        "title"
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"maintain": [{"text": "invalid"}]},
        {"intro": []},
        {"sections": "invalid"},
        {"credits": [{"role": "X", "members": [{"name": []}]}]},
    ],
)
async def test_invalid_homepage_body_rejected_atomically(
    client, make_user, track_content, body
):
    token = await token_for(client, make_user, UserRole.admin)
    created = await client.post(
        "/admin/content",
        headers=auth(token),
        json={"type": "homepage", "title": "Invalid homepage", "body": body},
    )
    assert created.status_code == 422
    original = await _create(
        client, token, track_content, type="homepage", title="Safe"
    )
    url = f"/admin/content/{original['id']}"
    assert (
        await client.patch(url, headers=auth(token), json={"body": body})
    ).status_code == 422
    assert (await client.get(url, headers=auth(token))).json()["body"] == {}


async def test_account_lock_permanently_revokes_previous_sessions(client, make_user):
    account = await make_user(role=UserRole.member)
    login = await client.post(
        "/auth/login", data={"username": account.email, "password": "secret123"}
    )
    previous = auth(login.json()["access_token"])
    admin = await token_for(client, make_user, UserRole.admin)
    for active in [False, True]:
        assert (
            await client.patch(
                f"/admin/users/{account.id}",
                headers=auth(admin),
                json={"is_active": active},
            )
        ).status_code == 200
        assert (await client.get("/auth/me", headers=previous)).status_code == 401


async def test_simultaneous_save_is_idempotent(client, make_user, make_content):
    from app.models.enums import ContentType

    post = await make_content(type_=ContentType.community)
    token = await token_for(client, make_user, UserRole.member)
    responses = await asyncio.gather(
        *[
            client.put(f"/api/community/{post.id}/save", headers=auth(token))
            for _ in range(2)
        ]
    )
    assert [r.status_code for r in responses] == [200, 200]


async def test_media_delete_waits_for_attachment_and_rechecks_usage(
    client, make_user, make_media, track_content
):
    token = await token_for(client, make_user, UserRole.admin)
    image = await make_media()
    # Hold the same lock used by _replace_media before linking the asset.
    async with SessionLocal() as attaching:
        await attaching.scalar(
            select(Media.id)
            .where(Media.id == image.id)
            .with_for_update(read=True, key_share=True)
        )
        deletion = asyncio.create_task(
            client.delete(f"/admin/media/{image.id}", headers=auth(token))
        )
        await asyncio.sleep(0.1)
        assert not deletion.done(), "Deletion must wait for the attachment transaction"
        from app.models.enums import ContentType
        from app.schemas.admin import ContentCreate, ContentMediaIn

        content = await content_admin.create_content(
            attaching,
            ContentCreate(
                type=ContentType.gallery,
                title="Fake protected album",
                media=[ContentMediaIn(media_id=image.id)],
            ),
            author_id=None,
        )
        track_content.append(content.id)
    response = await asyncio.wait_for(deletion, 5)
    assert response.status_code == 409
    assert (
        await client.get(f"/admin/media/{image.id}", headers=auth(token))
    ).status_code == 200


async def test_websocket_reserves_capacity_before_waiting_and_releases_on_failure(
    monkeypatch,
):
    from app.routers import community as router

    entered, release = asyncio.Event(), asyncio.Event()

    async def lookup(*args):
        entered.set()
        await release.wait()
        return None

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class Socket:
        def __init__(self):
            self.headers = {}
            self.close = AsyncMock()

    monkeypatch.setattr(router, "SessionLocal", Session)
    monkeypatch.setattr(router.community, "get_published_community", lookup)
    monkeypatch.setattr(realtime, "_MAX_CONNECTIONS", 1)
    first, second = Socket(), Socket()
    task = asyncio.create_task(router.community_ws(first, 1))
    await entered.wait()
    assert realtime.connection_count() == 1
    await router.community_ws(second, 1)
    second.close.assert_awaited_with(code=1013)
    release.set()
    await task
    assert realtime.connection_count() == 0


async def test_redis_listener_recovers_after_initial_outage(monkeypatch):
    connected = asyncio.Event()
    attempt = 0

    class Pubsub:
        async def subscribe(self, channel):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise ConnectionError("fake outage")
            connected.set()

        async def listen(self):
            await asyncio.Event().wait()
            yield {}

        async def aclose(self):
            pass

    class Redis:
        def pubsub(self):
            return Pubsub()

        async def aclose(self):
            pass

    monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **k: Redis())
    await realtime.start()
    try:
        await asyncio.wait_for(connected.wait(), 4)
        assert attempt == 2 and realtime._redis_alive
    finally:
        await realtime.stop()


async def test_attachment_waits_for_deletion_and_returns_validation_error(
    client, make_user, make_media, track_content
):
    token = await token_for(client, make_user, UserRole.admin)
    image = await make_media()
    async with SessionLocal() as deleting:
        media = await deleting.scalar(
            select(Media).where(Media.id == image.id).with_for_update()
        )
        attaching = asyncio.create_task(
            client.post(
                "/admin/content",
                headers=auth(token),
                json={
                    "type": "gallery",
                    "title": "Fake racing attachment",
                    "media": [{"media_id": image.id}],
                },
            )
        )
        try:
            await asyncio.sleep(0.1)
            assert not attaching.done()
            await deleting.delete(media)
            await deleting.commit()
            response = await asyncio.wait_for(attaching, 5)
            assert response.status_code == 422
        finally:
            if not attaching.done():
                attaching.cancel()
                await asyncio.gather(attaching, return_exceptions=True)


async def test_lock_revokes_session_issued_by_inflight_login(
    client, make_user, monkeypatch
):
    from app.routers import auth as auth_router

    account = await make_user(role=UserRole.member)
    admin = await token_for(client, make_user, UserRole.admin)
    entered, release = asyncio.Event(), asyncio.Event()
    original = auth_router.run_in_threadpool

    async def paused_verify(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(auth_router, "run_in_threadpool", paused_verify)
    signing_in = asyncio.create_task(
        client.post(
            "/auth/login", data={"username": account.email, "password": "secret123"}
        )
    )
    await entered.wait()
    locking = asyncio.create_task(
        client.patch(
            f"/admin/users/{account.id}", headers=auth(admin), json={"is_active": False}
        )
    )
    try:
        await asyncio.sleep(0.1)
        assert not locking.done()
        release.set()
        login, locked = await asyncio.gather(signing_in, locking)
        assert login.status_code == locked.status_code == 200
        previous = auth(login.json()["access_token"])
        assert (
            await client.patch(
                f"/admin/users/{account.id}",
                headers=auth(admin),
                json={"is_active": True},
            )
        ).status_code == 200
        assert (await client.get("/auth/me", headers=previous)).status_code == 401
    finally:
        release.set()
        await asyncio.gather(signing_in, locking, return_exceptions=True)
