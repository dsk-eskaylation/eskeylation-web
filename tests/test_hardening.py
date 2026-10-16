"""Test tích hợp đợt củng cố bảo mật: embed lồng, ownership, media in-use,
cookie httpOnly + CSRF."""

import pytest

from app.models.enums import UserRole
from tests.test_cms_api import _create, auth, token_for

pytestmark = pytest.mark.integration


# ---------- validate_embeds đệ quy ----------


async def test_embed_long_trong_sections_bi_chan_422(client, make_user, track_content):
    token = await token_for(client, make_user, UserRole.author)
    r = await client.post(
        "/admin/content",
        json={
            "type": "homepage",
            "title": "Home evil embed",
            "body": {"sections": [{"video_url": "https://evil.example/x.mp4"}]},
        },
        headers=auth(token),
    )
    assert r.status_code == 422
    assert "Embed" in r.json()["detail"]


async def test_embed_long_hop_le_di_qua(client, make_user, track_content):
    token = await token_for(client, make_user, UserRole.author)
    data = await _create(
        client,
        token,
        track_content,
        type="homepage",
        title="Home embed ok",
        body={"sections": [{"video_url": "https://www.youtube.com/watch?v=abc"}]},
    )
    assert data["body"]["sections"][0]["video_url"].startswith(
        "https://www.youtube.com"
    )


# ---------- Ownership: author chỉ thao tác bài của mình ----------


async def test_author_khong_sua_duoc_bai_nguoi_khac(client, make_user, track_content):
    token_a = await token_for(client, make_user, UserRole.author)
    token_b = await token_for(client, make_user, UserRole.author)
    data = await _create(
        client,
        token_a,
        track_content,
        type="music",
        title="Bài của A",
        body={"artist": "DSK"},
    )
    cid = data["id"]

    # B (author) xem chi tiết / sửa / nhân bản -> 403
    assert (
        await client.get(f"/admin/content/{cid}", headers=auth(token_b))
    ).status_code == 403
    assert (
        await client.patch(
            f"/admin/content/{cid}", json={"title": "Deface"}, headers=auth(token_b)
        )
    ).status_code == 403
    assert (
        await client.post(f"/admin/content/{cid}/duplicate", headers=auth(token_b))
    ).status_code == 403

    # Chính chủ A sửa được
    r = await client.patch(
        f"/admin/content/{cid}", json={"title": "Bài của A sửa"}, headers=auth(token_a)
    )
    assert r.status_code == 200


async def test_editor_sua_duoc_bai_cua_author(client, make_user, track_content):
    token_a = await token_for(client, make_user, UserRole.author)
    editor = await token_for(client, make_user, UserRole.editor)
    data = await _create(
        client,
        token_a,
        track_content,
        type="music",
        title="Bài author, editor sửa",
        body={"artist": "DSK"},
    )
    r = await client.patch(
        f"/admin/content/{data['id']}",
        json={"title": "Editor đã sửa"},
        headers=auth(editor),
    )
    assert r.status_code == 200


# ---------- Media đang dùng không xoá được ----------


async def test_xoa_media_dang_dung_409(
    client, make_user, make_content, make_media, link_media
):
    token = await token_for(client, make_user, UserRole.editor)
    content = await make_content()
    media = await make_media()
    await link_media(content, media, is_primary=True)

    r = await client.delete(f"/admin/media/{media.id}", headers=auth(token))
    assert r.status_code == 409
    assert "đang được" in r.json()["detail"]


async def test_xoa_media_khong_gan_204(client, make_user, make_media, db):
    token = await token_for(client, make_user, UserRole.editor)
    media = await make_media()
    r = await client.delete(f"/admin/media/{media.id}", headers=auth(token))
    assert r.status_code == 204


# ---------- Cookie httpOnly + CSRF ----------


async def test_login_set_cookie_va_me_qua_cookie(client, make_user):
    user = await make_user(password="pw12345678")
    r = await client.post(
        "/auth/login", data={"username": user.email, "password": "pw12345678"}
    )
    assert r.status_code == 200
    # Cookie phiên (httpOnly) + cookie CSRF phải được set
    assert "esk_session" in r.cookies
    assert "esk_csrf" in r.cookies

    # /auth/me KHÔNG kèm Authorization header -> xác thực qua cookie
    r = await client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == user.email


async def test_mutating_qua_cookie_thieu_csrf_403(client, make_user, track_content):
    user = await make_user(password="pw12345678", role=UserRole.editor)
    await client.post(
        "/auth/login", data={"username": user.email, "password": "pw12345678"}
    )
    payload = {"type": "music", "title": "CSRF test", "body": {"artist": "DSK"}}

    # Có cookie phiên nhưng KHÔNG gửi X-CSRF-Token -> 403
    r = await client.post("/admin/content", json=payload)
    assert r.status_code == 403
    assert "CSRF" in r.json()["detail"]

    # Kèm X-CSRF-Token đúng (double-submit) -> 201
    csrf = client.cookies.get("esk_csrf")
    r = await client.post(
        "/admin/content", json=payload, headers={"X-CSRF-Token": csrf}
    )
    assert r.status_code == 201, r.text
    track_content.append(r.json()["id"])


async def test_logout_xoa_cookie(client, make_user):
    user = await make_user(password="pw12345678")
    await client.post(
        "/auth/login", data={"username": user.email, "password": "pw12345678"}
    )
    csrf = client.cookies.get("esk_csrf")
    r = await client.post("/auth/logout", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 204
    # Cookie đã bị xoá -> /auth/me 401
    r = await client.get("/auth/me")
    assert r.status_code == 401
