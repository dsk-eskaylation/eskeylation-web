"""Test tích hợp CMS API — CRUD, workflow publish, RBAC (chạy thật)."""

import pytest
from httpx import AsyncClient

from app.models.enums import UserRole

pytestmark = pytest.mark.integration


async def token_for(client: AsyncClient, make_user, role: UserRole) -> str:
    user = await make_user(password="pw", role=role)
    r = await client.post(
        "/auth/login", data={"username": user.email, "password": "pw"}
    )
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create(client, token, track, **payload) -> dict:
    r = await client.post("/admin/content", json=payload, headers=auth(token))
    assert r.status_code == 201, r.text
    data = r.json()
    track.append(data["id"])
    return data


# ---------- create ----------

async def test_create_sinh_slug_khong_dau_va_draft(client, make_user, track_content):
    token = await token_for(client, make_user, UserRole.author)
    data = await _create(
        client, token, track_content,
        type="music", title="Bản Nhạc Đầu", body={"artist": "DSK"},
    )
    assert data["status"] == "draft"
    assert data["slug"].startswith("ban-nhac-dau")
    assert data["author_id"] is not None


async def test_create_khong_auth_401(client):
    r = await client.post("/admin/content", json={"type": "music", "title": "x"})
    assert r.status_code == 401


async def test_create_voi_media_khong_ton_tai_422(client, make_user, track_content):
    token = await token_for(client, make_user, UserRole.author)
    r = await client.post(
        "/admin/content",
        json={
            "type": "gallery",
            "title": "Album",
            "media": [{"media_id": 99999999}],
        },
        headers=auth(token),
    )
    assert r.status_code == 422


# ---------- update ----------

async def test_update_partial(client, make_user, track_content):
    token = await token_for(client, make_user, UserRole.author)
    c = await _create(
        client, token, track_content, type="music", title="Gốc", body={"a": 1}
    )
    r = await client.patch(
        f"/admin/content/{c['id']}", json={"summary": "tóm tắt mới"},
        headers=auth(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == "tóm tắt mới"
    assert body["title"] == "Gốc"  # không đổi


# ---------- publish validation theo loại ----------

async def test_publish_music_thieu_artist_422(client, make_user, track_content):
    author = await token_for(client, make_user, UserRole.author)
    editor = await token_for(client, make_user, UserRole.editor)
    c = await _create(client, author, track_content, type="music", title="No artist")
    r = await client.post(f"/admin/content/{c['id']}/publish", headers=auth(editor))
    assert r.status_code == 422


async def test_publish_music_co_artist_200(client, make_user, track_content):
    author = await token_for(client, make_user, UserRole.author)
    editor = await token_for(client, make_user, UserRole.editor)
    c = await _create(
        client, author, track_content,
        type="music", title="Có artist", body={"artist": "DSK"},
    )
    r = await client.post(f"/admin/content/{c['id']}/publish", headers=auth(editor))
    assert r.status_code == 200
    assert r.json()["status"] == "published"
    assert r.json()["published_at"] is not None


async def test_publish_gallery_can_media(
    client, make_user, make_media, track_content
):
    author = await token_for(client, make_user, UserRole.author)
    editor = await token_for(client, make_user, UserRole.editor)
    # chưa media -> 422
    c = await _create(client, author, track_content, type="gallery", title="G1")
    r1 = await client.post(f"/admin/content/{c['id']}/publish", headers=auth(editor))
    assert r1.status_code == 422
    # có media -> 200
    media = await make_media()
    c2 = await _create(
        client, author, track_content,
        type="gallery", title="G2", media=[{"media_id": media.id}],
    )
    r2 = await client.post(f"/admin/content/{c2['id']}/publish", headers=auth(editor))
    assert r2.status_code == 200


async def test_publish_homepage_can_sections(client, make_user, track_content):
    author = await token_for(client, make_user, UserRole.author)
    editor = await token_for(client, make_user, UserRole.editor)
    c = await _create(client, author, track_content, type="homepage", title="H")
    assert (
        await client.post(f"/admin/content/{c['id']}/publish", headers=auth(editor))
    ).status_code == 422
    c2 = await _create(
        client, author, track_content,
        type="homepage", title="H2", body={"sections": [{"kind": "hero"}]},
    )
    assert (
        await client.post(f"/admin/content/{c2['id']}/publish", headers=auth(editor))
    ).status_code == 200


# ---------- RBAC ----------

async def test_author_khong_duoc_publish_403(client, make_user, track_content):
    author = await token_for(client, make_user, UserRole.author)
    c = await _create(
        client, author, track_content,
        type="music", title="A", body={"artist": "X"},
    )
    r = await client.post(f"/admin/content/{c['id']}/publish", headers=auth(author))
    assert r.status_code == 403


async def test_author_khong_duoc_xoa_403_editor_xoa_204(
    client, make_user, track_content
):
    author = await token_for(client, make_user, UserRole.author)
    editor = await token_for(client, make_user, UserRole.editor)
    c = await _create(client, author, track_content, type="music", title="Del")
    assert (
        await client.delete(f"/admin/content/{c['id']}", headers=auth(author))
    ).status_code == 403
    assert (
        await client.delete(f"/admin/content/{c['id']}", headers=auth(editor))
    ).status_code == 204


# ---------- workflow ----------

async def test_unpublish_va_archive(client, make_user, track_content):
    author = await token_for(client, make_user, UserRole.author)
    editor = await token_for(client, make_user, UserRole.editor)
    c = await _create(
        client, author, track_content,
        type="music", title="WF", body={"artist": "X"},
    )
    await client.post(f"/admin/content/{c['id']}/publish", headers=auth(editor))
    r1 = await client.post(
        f"/admin/content/{c['id']}/unpublish", headers=auth(editor)
    )
    assert r1.json()["status"] == "draft"
    r2 = await client.post(f"/admin/content/{c['id']}/archive", headers=auth(editor))
    assert r2.json()["status"] == "archived"


async def test_duplicate(client, make_user, make_media, track_content):
    author = await token_for(client, make_user, UserRole.author)
    media = await make_media()
    c = await _create(
        client, author, track_content,
        type="gallery", title="Bản gốc",
        media=[{"media_id": media.id, "caption": "cap"}],
    )
    r = await client.post(
        f"/admin/content/{c['id']}/duplicate", headers=auth(author)
    )
    assert r.status_code == 201
    copy = r.json()
    track_content.append(copy["id"])
    assert copy["id"] != c["id"]
    assert copy["title"].endswith("(copy)")
    assert copy["slug"] != c["slug"]
    assert len(copy["media"]) == 1
    assert copy["media"][0]["caption"] == "cap"


# ---------- media link + public phản ánh ----------

async def test_create_voi_media_link(client, make_user, make_media, track_content):
    token = await token_for(client, make_user, UserRole.author)
    media = await make_media(alt_text="anh")
    c = await _create(
        client, token, track_content,
        type="gallery", title="Có ảnh",
        media=[
            {
                "media_id": media.id,
                "caption": "ảnh 1",
                "position": 1,
                "is_primary": True,
            }
        ],
    )
    assert len(c["media"]) == 1
    assert c["media"][0]["caption"] == "ảnh 1"
    assert c["media"][0]["is_primary"] is True
    assert c["media"][0]["url"]


async def test_public_phan_anh_sau_publish(client, make_user, track_content):
    author = await token_for(client, make_user, UserRole.author)
    editor = await token_for(client, make_user, UserRole.editor)
    c = await _create(
        client, author, track_content,
        type="music", title="Public test", body={"artist": "DSK"},
    )
    slug = c["slug"]
    # chưa publish -> public 404
    assert (await client.get(f"/api/music/{slug}")).status_code == 404
    # publish -> public 200
    await client.post(f"/admin/content/{c['id']}/publish", headers=auth(editor))
    assert (await client.get(f"/api/music/{slug}")).status_code == 200
    # unpublish -> public 404 lại
    await client.post(f"/admin/content/{c['id']}/unpublish", headers=auth(editor))
    assert (await client.get(f"/api/music/{slug}")).status_code == 404
