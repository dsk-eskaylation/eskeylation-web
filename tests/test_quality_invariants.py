"""Generated input contracts and regressions found by the quality skill rollout."""

import asyncio
import io
import threading

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from hypothesis import example, given, settings
from hypothesis import strategies as st
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import delete

from app.main import app
from app.models.enums import ContentType, UserRole
from app.models.interaction_target import InteractionTarget
from app.schemas.admin import ContentUpdate
from app.services.sanitize import playable_video_embed, validate_embeds
from app.services.storage import get_storage
from tests.test_cms_api import auth, token_for


@given(field=st.sampled_from(["title", "body"]))
def test_required_update_fields_distinguish_omitted_from_null(field):
    assert ContentUpdate.model_validate({}).model_dump(exclude_unset=True) == {}
    with pytest.raises(ValidationError):
        ContentUpdate.model_validate({field: None})
    # Clearing an optional description remains supported.
    assert ContentUpdate(summary=None).model_dump(exclude_unset=True) == {
        "summary": None
    }


@settings(max_examples=100, deadline=None)
@example(url="https://[")
@example(url="https://example.invalid:bad/watch?v=abcdefghijk")
@given(
    url=st.builds(
        lambda label, scheme, trick: (
            f"{scheme}://{trick}{label}.invalid/watch?v=abcdefghijk"
        ),
        label=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=30
        ),
        scheme=st.sampled_from(["http", "https", "file"]),
        trick=st.sampled_from(["", "youtube.com@", "vimeo.com@"]),
    )
)
def test_untrusted_video_urls_never_pass_nested_embed_validation(url):
    assert not playable_video_embed(url)
    with pytest.raises(HTTPException) as error:
        validate_embeds({"sections": [{"nested": {"embed_url": url}}]})
    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "payload", [{"title": None}, {"body": None}, {"body": {"embed_url": "https://["}}]
)
async def test_rejected_patch_does_not_change_published_content(
    client, make_user, make_content, payload
):
    token = await token_for(client, make_user, UserRole.admin)
    content = await make_content(
        body={"artist": "Fake", "audio_url": "/media/fake.mp3"},
        summary="Fake original summary",
    )
    url = f"/admin/content/{content.id}"
    before = (await client.get(url, headers=auth(token))).json()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as requests:
        response = await requests.patch(
            url, headers=auth(token), json={"summary": "Must not be saved", **payload}
        )
    assert response.status_code == 422
    after = (await client.get(url, headers=auth(token))).json()
    assert (after["title"], after["body"], after["summary"]) == (
        before["title"],
        before["body"],
        before["summary"],
    )


@pytest.mark.parametrize(
    ("kind", "mime", "extension"),
    [
        (ContentType.music, "audio/mpeg", ".mp3"),
        (ContentType.video, "video/mp4", ".mp4"),
    ],
)
async def test_legacy_stream_chooses_playable_file_when_cover_is_primary(
    client, db, make_content, make_media, link_media, kind, mime, extension
):
    content = await make_content(type_=kind, body={"artist": "Fake"})
    cover = await make_media()
    playable = await make_media(
        mime_type=mime, storage_key=f"fake-stream-{content.id}{extension}"
    )
    await link_media(content, cover, position=0, is_primary=True)
    await link_media(content, playable, position=1)
    public_id = -9000000 - content.id
    await db.execute(
        delete(InteractionTarget).where(InteractionTarget.content_id == content.id)
    )
    db.add(
        InteractionTarget(
            id=public_id,
            content_id=content.id,
            drive_file_id=f"fake-legacy-{content.id}",
        )
    )
    await db.commit()
    for method in ["GET", "HEAD"]:
        response = await client.request(
            method, f"/api/library/{public_id}/stream", follow_redirects=False
        )
        assert response.status_code == 307
        assert response.headers["location"] == get_storage().url(playable.storage_key)
    image = await client.get(f"/api/library/{public_id}/image", follow_redirects=False)
    assert image.headers["location"] == get_storage().url(cover.storage_key)


async def test_slow_storage_upload_does_not_block_health_request(
    client, make_user, monkeypatch, track_media
):
    from app.services import media as media_service

    token = await token_for(client, make_user, UserRole.admin)
    started, release, finished = threading.Event(), threading.Event(), threading.Event()

    class SlowStorage:
        def save(self, key, _data):
            started.set()
            release.wait(timeout=5)
            finished.set()
            return f"/media/{key}"

    monkeypatch.setattr(media_service, "get_storage", lambda: SlowStorage())
    data = io.BytesIO()
    Image.new("RGB", (20, 20), "orange").save(data, "PNG")
    upload = asyncio.create_task(
        client.post(
            "/admin/media",
            headers=auth(token),
            files={"file": ("fake.png", data.getvalue(), "image/png")},
        )
    )
    try:
        assert await asyncio.to_thread(started.wait, 5)
        assert (await client.get("/health")).status_code == 200
        assert not finished.is_set(), "Slow storage blocked the event loop"
    finally:
        release.set()
        response = await upload
        assert response.status_code == 201
        track_media.append(response.json()["id"])
