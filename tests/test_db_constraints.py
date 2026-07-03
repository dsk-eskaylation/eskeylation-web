"""Test tích hợp DB hardening (docs/db-review.md):
validate CMS chặn input vi phạm + constraint DB là lưới an toàn cuối."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.enums import ContentStatus, ContentType, UserRole
from app.models.media import ContentMedia
from app.services import content_admin
from tests.test_cms_api import _create, auth, token_for

pytestmark = pytest.mark.integration


# ---------- Validate ở tầng service/API (trả 422, không nổ 500) ----------


async def test_hai_primary_bi_chan_422(
    client, make_user, make_media, track_content
):
    token = await token_for(client, make_user, UserRole.author)
    m1 = await make_media()
    m2 = await make_media()
    r = await client.post(
        "/admin/content",
        json={
            "type": "gallery",
            "title": "Album 2 primary",
            "media": [
                {"media_id": m1.id, "is_primary": True},
                {"media_id": m2.id, "is_primary": True, "position": 1},
            ],
        },
        headers=auth(token),
    )
    assert r.status_code == 422
    assert "primary" in r.json()["detail"]


async def test_media_gan_trung_bi_chan_422(
    client, make_user, make_media, track_content
):
    token = await token_for(client, make_user, UserRole.author)
    m = await make_media()
    r = await client.post(
        "/admin/content",
        json={
            "type": "gallery",
            "title": "Album media trùng",
            "media": [
                {"media_id": m.id, "is_primary": True},
                {"media_id": m.id, "position": 1},
            ],
        },
        headers=auth(token),
    )
    assert r.status_code == 422
    assert "trùng" in r.json()["detail"]


async def test_position_duoc_chuan_hoa_0_n(
    client, make_user, make_media, track_content
):
    # Gửi position 7 và 3 → lưu thành 0..1 theo thứ tự client yêu cầu (3 trước 7)
    token = await token_for(client, make_user, UserRole.author)
    m1 = await make_media()
    m2 = await make_media()
    data = await _create(
        client,
        token,
        track_content,
        type="gallery",
        title="Album chuẩn hoá position",
        media=[
            {"media_id": m1.id, "position": 7, "is_primary": True},
            {"media_id": m2.id, "position": 3},
        ],
    )
    got = {item["media_id"]: item["position"] for item in data["media"]}
    assert got == {m2.id: 0, m1.id: 1}


# ---------- set_status không được lách publish (M1) ----------


async def test_set_status_published_di_qua_validate_va_set_published_at(
    db, make_content
):
    content = await make_content(
        type_=ContentType.music,
        status=ContentStatus.draft,
        body={"artist": "DSK"},
        published=False,
    )
    updated = await content_admin.set_status(db, content, ContentStatus.published)
    assert updated.status == ContentStatus.published
    assert updated.published_at is not None


async def test_set_status_published_thieu_metadata_422(db, make_content):
    # music không có artist → validate_for_publish phải chặn dù đi đường set_status
    from fastapi import HTTPException

    content = await make_content(
        type_=ContentType.music,
        status=ContentStatus.draft,
        body={},
        published=False,
    )
    with pytest.raises(HTTPException) as exc:
        await content_admin.set_status(db, content, ContentStatus.published)
    assert exc.value.status_code == 422


# ---------- Constraint DB là lưới an toàn cuối ----------


async def test_db_chan_media_gan_trung(db, make_content, make_media):
    content = await make_content(
        type_=ContentType.gallery, status=ContentStatus.draft, published=False
    )
    m = await make_media()
    db.add(ContentMedia(content_id=content.id, media_id=m.id, position=0))
    db.add(ContentMedia(content_id=content.id, media_id=m.id, position=1))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_db_chan_hai_primary(db, make_content, make_media):
    content = await make_content(
        type_=ContentType.gallery, status=ContentStatus.draft, published=False
    )
    m1 = await make_media()
    m2 = await make_media()
    db.add(
        ContentMedia(
            content_id=content.id, media_id=m1.id, position=0, is_primary=True
        )
    )
    db.add(
        ContentMedia(
            content_id=content.id, media_id=m2.id, position=1, is_primary=True
        )
    )
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_db_chan_published_thieu_published_at(db, make_content):
    content = await make_content(
        type_=ContentType.music,
        status=ContentStatus.draft,
        body={"artist": "DSK"},
        published=False,
    )
    content.status = ContentStatus.published  # cố tình lách, không set published_at
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_db_cho_phep_slug_trung_khac_type(db, make_content):
    from tests.conftest import unique_slug as rand_slug

    base = rand_slug("dupslug")
    await make_content(
        slug=base,
        type_=ContentType.music,
        status=ContentStatus.draft,
        published=False,
    )
    # Cùng slug, khác type → hợp lệ với UNIQUE(type, slug)
    c2 = await make_content(
        slug=base,
        type_=ContentType.gallery,
        status=ContentStatus.draft,
        published=False,
    )
    assert c2.slug == base
