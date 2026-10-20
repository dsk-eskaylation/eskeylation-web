"""Regressions for publishing invalid assets and reviewing contributed lyrics."""

import asyncio

import pytest
from sqlalchemy import delete, select

from app.models.activity import ActivityLog
from app.models.enums import UserRole
from app.models.interaction_target import InteractionTarget
from app.models.lyrics import LyricSuggestion
from app.services.sanitize import playable_video_embed
from tests.test_cms_api import _create, auth, token_for


@pytest.mark.parametrize(
    ("kind", "body", "mime"),
    [
        ("music", {"artist": "Fake"}, None),
        ("music", {"artist": "Fake", "audio_url": "javascript:alert(1)"}, None),
        (
            "music",
            {"artist": "Fake", "embed_url": "https://youtu.be/abcdefghijk"},
            None,
        ),
        ("music", {"artist": "   "}, "audio/mpeg"),
        ("video", {}, None),
        ("video", {}, "image/png"),
        ("video", {"embed_url": "https://www.youtube.com/"}, None),
        ("gallery", {}, "audio/mpeg"),
    ],
)
async def test_invalid_source_can_save_draft_but_cannot_publish(
    client, make_user, make_media, track_content, kind, body, mime
):
    token = await token_for(client, make_user, UserRole.admin)
    media = await make_media(mime_type=mime) if mime else None
    content = await _create(
        client,
        token,
        track_content,
        type=kind,
        title="Fake invalid source",
        body=body,
        media=[{"media_id": media.id}] if media else [],
    )
    response = await client.post(
        f"/admin/content/{content['id']}/publish", headers=auth(token)
    )
    assert response.status_code == 422
    assert (
        await client.get(f"/admin/content/{content['id']}", headers=auth(token))
    ).json()["status"] == "draft"


@pytest.mark.parametrize(
    ("kind", "mime"),
    [("music", "audio/mpeg"), ("video", "video/mp4"), ("gallery", "image/png")],
)
async def test_replacing_published_asset_validates_and_rolls_back_invalid_edit(
    client, make_user, make_media, track_content, kind, mime
):
    token = await token_for(client, make_user, UserRole.admin)
    first = await make_media(mime_type=mime)
    second = await make_media(mime_type=mime)
    wrong = await make_media(mime_type="application/pdf")
    c = await _create(
        client,
        token,
        track_content,
        type=kind,
        title="Fake valid source",
        body={"artist": "Fake"},
        media=[{"media_id": first.id}],
    )
    url = f"/admin/content/{c['id']}"
    assert (await client.post(url + "/publish", headers=auth(token))).status_code == 200
    assert (
        await client.patch(
            url, json={"media": [{"media_id": second.id}]}, headers=auth(token)
        )
    ).status_code == 200
    before = (await client.get(url, headers=auth(token))).json()
    invalid = await client.patch(
        url,
        json={"title": "Must roll back", "media": [{"media_id": wrong.id}]},
        headers=auth(token),
    )
    assert invalid.status_code == 422
    after = (await client.get(url, headers=auth(token))).json()
    assert after["title"] == before["title"]
    assert after["media"] == before["media"]


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=abcdefghijk",
        "https://youtu.be/abcdefghijk",
        "https://www.youtube.com/embed/abcdefghijk",
        "https://www.youtube.com/shorts/abcdefghijk",
        "https://vimeo.com/12345",
        "https://player.vimeo.com/video/12345",
    ],
)
async def test_supported_embeds_can_publish(client, make_user, track_content, url):
    assert playable_video_embed(url)
    token = await token_for(client, make_user, UserRole.admin)
    c = await _create(
        client,
        token,
        track_content,
        type="video",
        title="Fake embed",
        body={"embed_url": url},
    )
    assert (
        await client.post(f"/admin/content/{c['id']}/publish", headers=auth(token))
    ).status_code == 200


@pytest.mark.parametrize(
    "url",
    [
        None,
        {},
        "https://www.youtube.com/",
        "https://vimeo.com/",
        "https://evilvimeo.com/1234",
        "javascript:alert(1)",
        "https://www.youtube.com/embed/",
    ],
)
def test_invalid_embed_is_not_playable(url):
    assert not playable_video_embed(url)


async def song_and_suggestion(client, make_user, track_content, db, *, negative=False):
    admin = await token_for(client, make_user, UserRole.admin)
    c = await _create(
        client,
        admin,
        track_content,
        type="music",
        title="Fake lyric song",
        body={
            "artist": "Fake",
            "audio_url": "/media/fake.mp3",
            "lyrics": "Original fake lyrics",
        },
    )
    assert (
        await client.post(f"/admin/content/{c['id']}/publish", headers=auth(admin))
    ).status_code == 200
    public_id = c["id"]
    if negative:
        public_id = -99123456700 - c["id"]
        await db.execute(
            delete(InteractionTarget).where(InteractionTarget.content_id == c["id"])
        )
        db.add(
            InteractionTarget(
                id=public_id, content_id=c["id"], drive_file_id=f"fake-{c['id']}"
            )
        )
        await db.commit()
    member = await token_for(client, make_user, UserRole.member)
    response = await client.post(
        f"/api/music/{public_id}/lyrics",
        json={"body": "Fake contribution\nSecond line"},
        headers=auth(member),
    )
    assert response.status_code == 201
    queue = await client.get("/admin/moderation/lyrics", headers=auth(admin))
    assert queue.status_code == 200
    item = next(x for x in queue.json()["items"] if x["content_id"] == public_id)
    assert item["cms_content_id"] == c["id"] and item["can_accept"]
    return admin, member, c, item


@pytest.mark.parametrize("negative", [False, True])
async def test_admin_accept_updates_right_song_and_catalog_and_writes_log(
    client, make_user, track_content, db, negative
):
    admin, member, song, item = await song_and_suggestion(
        client, make_user, track_content, db, negative=negative
    )
    url = f"/admin/moderation/lyrics/{item['id']}"
    before = (await client.get("/api/catalog")).json()["revision"]
    for role in [UserRole.member, UserRole.author, UserRole.editor]:
        token = (
            member
            if role == UserRole.member
            else await token_for(client, make_user, role)
        )
        assert (
            await client.get("/admin/moderation/lyrics", headers=auth(token))
        ).status_code == 403
        assert (
            await client.patch(url, json={"status": "accepted"}, headers=auth(token))
        ).status_code == 403
    accepted = await client.patch(url, json={"status": "accepted"}, headers=auth(admin))
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    public = (await client.get(f"/api/music/{song['slug']}")).json()
    assert public["id"] == item["content_id"]
    assert public["body"]["lyrics"] == item["body"]
    assert public["body"]["artist"] == "Fake"
    assert (await client.get("/api/catalog")).json()["revision"] != before
    assert (
        await client.patch(url, json={"status": "rejected"}, headers=auth(admin))
    ).status_code == 409
    history = (
        await client.get(
            "/admin/moderation/lyrics?review_status=accepted&page_size=1",
            headers=auth(admin),
        )
    ).json()
    assert history["page_size"] == 1 and history["total"] >= 1
    log = await db.scalar(
        select(ActivityLog).where(
            ActivityLog.entity_type == "lyric_suggestion",
            ActivityLog.entity_id == item["id"],
        )
    )
    assert log.action == "lyrics_accept" and log.detail["cms_content_id"] == song["id"]


async def test_reject_keeps_current_lyrics_and_requires_pending_status(
    client, make_user, track_content, db
):
    admin, _, song, item = await song_and_suggestion(
        client, make_user, track_content, db
    )
    url = f"/admin/moderation/lyrics/{item['id']}"
    assert (
        await client.patch(url, json={"status": "pending"}, headers=auth(admin))
    ).status_code == 422
    assert (
        await client.patch(url, json={"status": "rejected"}, headers=auth(admin))
    ).status_code == 200
    assert (await client.get(f"/api/music/{song['slug']}")).json()["body"][
        "lyrics"
    ] == "Original fake lyrics"
    assert (
        await client.patch(url, json={"status": "accepted"}, headers=auth(admin))
    ).status_code == 409
    assert (
        await client.patch(
            "/admin/moderation/lyrics/999999999",
            json={"status": "accepted"},
            headers=auth(admin),
        )
    ).status_code == 404


async def test_concurrent_review_only_one_decision_succeeds(
    client, make_user, track_content, db
):
    admin, _, _, item = await song_and_suggestion(client, make_user, track_content, db)
    responses = await asyncio.gather(
        *[
            client.patch(
                f"/admin/moderation/lyrics/{item['id']}",
                json={"status": decision},
                headers=auth(admin),
            )
            for decision in ["accepted", "rejected"]
        ]
    )
    assert sorted(r.status_code for r in responses) == [200, 409]


async def test_review_validates_banned_words_without_consuming_suggestion(
    client, make_user, track_content, db
):
    admin, _, song, item = await song_and_suggestion(
        client, make_user, track_content, db
    )
    word = await client.post(
        "/admin/moderation/banned-words",
        headers=auth(admin),
        json={"word": "contribution"},
    )
    assert word.status_code == 201
    try:
        response = await client.patch(
            f"/admin/moderation/lyrics/{item['id']}",
            headers=auth(admin),
            json={"status": "accepted"},
        )
        assert response.status_code == 422
        await db.refresh(await db.get(LyricSuggestion, item["id"]))
        assert (await db.get(LyricSuggestion, item["id"])).status == "pending"
        public = (await client.get(f"/api/music/{song['slug']}")).json()
        assert public["body"]["lyrics"] == "Original fake lyrics"
    finally:
        await client.delete(
            f"/admin/moderation/banned-words/{word.json()['id']}", headers=auth(admin)
        )


async def test_unmapped_contribution_can_only_be_rejected(client, make_user, db):
    admin = await token_for(client, make_user, UserRole.admin)
    target_id = -991111000011
    db.add(InteractionTarget(id=target_id, drive_file_id="fake-unmapped-lyric"))
    await db.flush()
    suggestion = LyricSuggestion(content_id=target_id, body="Fake orphan", user_id=None)
    db.add(suggestion)
    await db.commit()
    try:
        url = f"/admin/moderation/lyrics/{suggestion.id}"
        assert (
            await client.patch(url, json={"status": "accepted"}, headers=auth(admin))
        ).status_code == 409
        assert (
            await client.patch(url, json={"status": "rejected"}, headers=auth(admin))
        ).status_code == 200
    finally:
        await db.execute(
            delete(InteractionTarget).where(InteractionTarget.id == target_id)
        )
        await db.commit()
