"""Regression coverage for existing Drive interactions after the CMS/S3 cutover."""

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models.community import Comment, PostReaction, SavedPost
from app.models.content import Content
from app.models.enums import ContentType, ReactionType
from app.models.interaction_target import InteractionTarget
from app.models.media import Media
from app.services.catalog_revision import database_revision
from app.services.content_migration import import_drive_content
from app.services.drive_catalog import file_to_content
from tests.conftest import unique_slug
from tests.test_community_api import auth, token_for

pytestmark = pytest.mark.integration


def migration_item(type_=ContentType.community):
    file_id = unique_slug("s3-drive")
    original = file_to_content(
        {"id": file_id, "name": "Preserved.jpg", "mimeType": "image/jpeg"},
        ["Cộng đồng" if type_ == ContentType.community else "Nhạc & MV"],
    )
    return {
        "public_id": original.id,
        "drive_file_id": file_id,
        "type": type_.value,
        "title": original.title,
        "slug": original.slug,
        "summary": "Preserved summary",
        "body": {"source": "s3", "artist": "Test"},
        "media": [
            {
                "storage_key": f"drive/{file_id}/display.webp",
                "mime_type": "image/webp",
                "size": 100,
                "width": 3840,
                "height": 2160,
                "duration": None,
                "is_primary": True,
                "alt_text": "Preserved image",
            }
        ],
    }


async def test_migration_preserves_comments_reactions_saves_and_legacy_urls(
    client, db, make_user, track_content, track_media, monkeypatch
):
    user, token = await token_for(client, make_user)
    item = migration_item()
    public_id = item["public_id"]
    db.add(InteractionTarget(id=public_id, drive_file_id=item["drive_file_id"]))
    await db.flush()
    db.add_all(
        [
            Comment(content_id=public_id, user_id=user.id, body="Existing comment"),
            PostReaction(content_id=public_id, user_id=user.id, type=ReactionType.love),
            SavedPost(content_id=public_id, user_id=user.id),
        ]
    )
    await db.commit()
    internal_id, created = await import_drive_content(db, item, user.id)
    await db.commit()
    track_content.append(internal_id)
    track_media.extend(
        (
            await db.scalars(
                select(Media.id).where(
                    Media.storage_key.startswith("drive/" + item["drive_file_id"])
                )
            )
        ).all()
    )
    assert created
    again, created = await import_drive_content(db, item, user.id)
    assert again == internal_id and not created
    await db.commit()
    detail = await client.get(f"/api/community/{item['slug']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == public_id
    assert (await client.get(f"/api/community/{public_id}/comments")).json()["items"][
        0
    ]["body"] == "Existing comment"
    overview = await client.get(
        f"/api/community/{public_id}/interactions", headers=auth(token)
    )
    assert overview.status_code == 200
    assert overview.json()["saved"] is True
    assert overview.json()["reactions"]["total"] == 1
    assert (
        await client.get(f"/api/community/{internal_id}/interactions")
    ).status_code == 404
    monkeypatch.setattr(get_settings(), "storage_backend", "s3")
    monkeypatch.setattr(get_settings(), "s3_bucket", "test-s3-migration")
    monkeypatch.setattr(get_settings(), "s3_cdn_url", "https://test.cloudfront.net")
    legacy = await client.get(f"/api/library/{public_id}/image?w=640")
    assert legacy.status_code == 307
    assert legacy.headers["location"].startswith(
        "https://test.cloudfront.net/cms/drive/"
    )
    content = await db.get(Content, internal_id)
    from app.models.enums import ContentStatus

    content.status = ContentStatus.archived
    await db.commit()
    assert (
        await client.get(f"/api/library/{public_id}/image?w=640")
    ).status_code == 404
    assert (
        await client.get(f"/api/community/{public_id}/interactions")
    ).status_code == 404
    # Restore the local backend before the tracked-media teardown removes files.
    monkeypatch.setattr(get_settings(), "storage_backend", "local")


async def test_database_revision_tracks_media_replacement_and_unpublish(
    db, make_content, make_media, link_media
):
    from app.models.enums import ContentStatus

    content = await make_content()
    before = await database_revision(db)
    media = await make_media()
    link = await link_media(content, media)
    after_media = await database_revision(db)
    assert after_media != before
    link.caption = "Changed caption"
    await db.commit()
    assert await database_revision(db) != after_media
    content.status = ContentStatus.archived
    await db.commit()
    assert await database_revision(db) != before
