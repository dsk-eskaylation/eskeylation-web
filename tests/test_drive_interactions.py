"""Tương tác thật trên PostgreSQL; nội dung Drive chỉ được giả lập metadata."""

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from app.config import get_settings
from app.models.content import Content
from app.models.interaction_target import InteractionTarget
from app.services.drive_catalog import catalog, file_to_content
from tests.conftest import unique_slug
from tests.test_community_api import auth, token_for

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def drive_posts(monkeypatch, db):
    monkeypatch.setattr(get_settings(), "public_content_source", "drive")
    post = file_to_content(
        {"id": unique_slug("drive"), "name": "Fanmade.jpg", "mimeType": "image/jpeg"},
        ["Cộng đồng"],
    )
    music = file_to_content(
        {"id": unique_slug("drive"), "name": "Song.mp3", "mimeType": "audio/mpeg"},
        ["Nhạc & MV"],
    )
    items = AsyncMock(return_value=[post, music])
    monkeypatch.setattr(catalog, "items", items)
    yield post, music, items
    await db.execute(
        delete(InteractionTarget).where(InteractionTarget.id.in_([post.id, music.id]))
    )
    await db.commit()


async def test_drive_reactions_comments_saves_and_lyrics_without_import(
    client, db, make_user, drive_posts
):
    post, music, items = drive_posts
    _, token = await token_for(client, make_user)
    headers = auth(token)
    before = await db.scalar(select(func.count()).select_from(Content))
    base = f"/api/community/{post.id}"

    overview = await client.get(f"{base}/interactions", headers=headers)
    assert overview.status_code == 200, overview.text
    assert overview.json()["reactions"]["total"] == 0
    reaction = await client.put(
        f"{base}/reaction", json={"type": "love"}, headers=headers
    )
    assert reaction.status_code == 200, reaction.text
    assert reaction.json()["my_reaction"] == "love"
    comment = await client.post(
        f"{base}/comments", json={"body": "Nice!"}, headers=headers
    )
    assert comment.status_code == 201, comment.text
    comment_id = comment.json()["id"]
    edited = await client.patch(
        f"{base}/comments/{comment_id}", json={"body": "Edited!"}, headers=headers
    )
    assert edited.status_code == 200, edited.text
    assert (await client.get(f"{base}/comments")).json()["items"][0][
        "body"
    ] == "Edited!"
    saved = await client.put(f"{base}/save", headers=headers)
    assert saved.status_code == 200, saved.text
    overview = (await client.get(f"{base}/interactions", headers=headers)).json()
    assert overview["comment_count"] == 1
    assert overview["saved"] is True
    assert overview["reactions"]["total"] == 1
    lyric = await client.post(
        f"/api/music/{music.id}/lyrics",
        json={"body": "Suggested lyrics"},
        headers=headers,
    )
    assert lyric.status_code == 201, lyric.text
    assert await db.scalar(select(func.count()).select_from(Content)) == before
    target = await db.get(InteractionTarget, post.id)
    assert target.content_id is None
    assert target.drive_file_id == post._drive["id"]

    # File bị gỡ khỏi thư mục công khai thì tương tác cũng không được truy cập.
    items.return_value = [music]
    assert (await client.get(f"{base}/interactions")).status_code == 404
    assert (
        await client.post(f"{base}/comments", json={"body": "No"}, headers=headers)
    ).status_code == 404


async def test_drive_comment_ownership_and_wrong_content_type(
    client, make_user, drive_posts
):
    post, music, _ = drive_posts
    _, owner = await token_for(client, make_user)
    _, other = await token_for(client, make_user)
    base = f"/api/community/{post.id}"
    created = await client.post(
        f"{base}/comments", json={"body": "Owner"}, headers=auth(owner)
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    edit = await client.patch(
        f"{base}/comments/{cid}", json={"body": "Other"}, headers=auth(other)
    )
    assert edit.status_code == 403
    # Bài nhạc Drive cũng nhận cảm xúc (dùng chung tương tác với cộng đồng).
    music_reaction = await client.put(
        f"/api/community/{music.id}/reaction",
        json={"type": "like"},
        headers=auth(owner),
    )
    assert music_reaction.status_code == 200, music_reaction.text
