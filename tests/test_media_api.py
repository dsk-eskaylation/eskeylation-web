"""Test tích hợp Media Manager — upload, validate, list, delete (chạy thật)."""

import io

import pytest
from httpx import AsyncClient
from PIL import Image

from app.models.enums import UserRole

pytestmark = pytest.mark.integration


def png_bytes(size=(12, 8), color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


async def _token(client: AsyncClient, make_user, role=UserRole.author) -> str:
    user = await make_user(password="pw", role=role)
    r = await client.post(
        "/auth/login", data={"username": user.email, "password": "pw"}
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------- auth ----------


async def test_upload_khong_auth_tra_401(client):
    r = await client.post(
        "/admin/media", files={"file": ("a.png", png_bytes(), "image/png")}
    )
    assert r.status_code == 401


# ---------- upload hợp lệ ----------


async def test_upload_anh_hop_le(client, make_user, track_media):
    token = await _token(client, make_user)
    r = await client.post(
        "/admin/media",
        files={"file": ("anh.png", png_bytes((20, 10)), "image/png")},
        data={"alt_text": "mô tả"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    body = r.json()
    track_media.append(body["id"])
    assert body["mime_type"] == "image/png"
    assert body["width"] == 20 and body["height"] == 10
    assert body["alt_text"] == "mô tả"
    assert body["url"].endswith(".png")


# ---------- validate ----------


async def test_upload_dinh_dang_khong_ho_tro_tra_415(client, make_user):
    token = await _token(client, make_user)
    r = await client.post(
        "/admin/media",
        files={"file": ("a.txt", b"chi la van ban", "text/plain")},
        headers=_auth(token),
    )
    assert r.status_code == 415


async def test_upload_khong_tin_duoi_file(client, make_user):
    # File .png nhưng nội dung là text → filetype phát hiện theo magic bytes → 415
    token = await _token(client, make_user)
    r = await client.post(
        "/admin/media",
        files={"file": ("gia.png", b"khong phai anh", "image/png")},
        headers=_auth(token),
    )
    assert r.status_code == 415


async def test_upload_file_rong_tra_400(client, make_user):
    token = await _token(client, make_user)
    r = await client.post(
        "/admin/media",
        files={"file": ("rong.png", b"", "image/png")},
        headers=_auth(token),
    )
    assert r.status_code == 400


def mp4_bytes() -> bytes:
    # Box ftyp tối thiểu để filetype.guess nhận diện là video/mp4.
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 16


async def test_upload_video_mp4(client, make_user, track_media):
    token = await _token(client, make_user)
    r = await client.post(
        "/admin/media",
        files={"file": ("clip.mp4", mp4_bytes(), "video/mp4")},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    track_media.append(body["id"])
    assert body["mime_type"] == "video/mp4"
    # video chưa lấy dimensions/duration ở bước này
    assert body["width"] is None
    assert body["height"] is None
    assert body["url"].endswith(".mp4")


async def test_upload_mp3_detects_bytes_and_publishes_attached_audio(
    client, make_user, track_media, track_content
):
    token = await _token(client, make_user, UserRole.admin)
    # MPEG audio frame signature; the browser suite uses a real audio fixture.
    audio = b"\xff\xfb\x90\x64" + b"\0" * 1024
    uploaded = await client.post(
        "/admin/media",
        files={"file": ("misleading.png", audio, "image/png")},
        headers=_auth(token),
    )
    assert uploaded.status_code == 201, uploaded.text
    media = uploaded.json()
    track_media.append(media["id"])
    assert media["mime_type"] == "audio/mpeg"
    assert media["url"].endswith(".mp3")
    created = await client.post(
        "/admin/content",
        json={
            "type": "music",
            "title": "Attached MP3",
            "body": {"artist": "Test", "audio_url": "https://old.invalid/old.mp3"},
            "media": [{"media_id": media["id"], "is_primary": True}],
        },
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    content = created.json()
    track_content.append(content["id"])
    published = await client.post(
        f"/admin/content/{content['id']}/publish", headers=_auth(token)
    )
    assert published.status_code == 200, published.text
    public = await client.get(f"/api/music/{content['slug']}")
    assert public.status_code == 200
    assert public.json()["body"]["audio_url"] == media["url"]
    assert public.json()["media"][0]["mime_type"] == "audio/mpeg"


async def test_mp3_size_cap_is_enforced(client, make_user, monkeypatch):
    from app.services.media import settings

    monkeypatch.setattr(settings, "max_audio_size", 16)
    token = await _token(client, make_user)
    response = await client.post(
        "/admin/media",
        files={"file": ("large.mp3", b"\xff\xfb\x90\x64" + b"\0" * 100, "audio/mpeg")},
        headers=_auth(token),
    )
    assert response.status_code == 413


async def test_upload_anh_hong_tra_400(client, make_user):
    # Magic bytes PNG hợp lệ nhưng nội dung hỏng → Pillow từ chối → 400
    token = await _token(client, make_user)
    corrupt = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    r = await client.post(
        "/admin/media",
        files={"file": ("hong.png", corrupt, "image/png")},
        headers=_auth(token),
    )
    assert r.status_code == 400


async def test_upload_vuot_size_tra_413(client, make_user, monkeypatch):
    from app.services import media as media_service

    monkeypatch.setattr(media_service.settings, "max_image_size", 100)
    token = await _token(client, make_user)
    r = await client.post(
        "/admin/media",
        files={"file": ("to.png", png_bytes((300, 300)), "image/png")},
        headers=_auth(token),
    )
    assert r.status_code == 413


# ---------- list / get / delete ----------


async def test_list_chua_media_vua_upload(client, make_user, track_media):
    token = await _token(client, make_user)
    up = await client.post(
        "/admin/media",
        files={"file": ("x.png", png_bytes(), "image/png")},
        headers=_auth(token),
    )
    mid = up.json()["id"]
    track_media.append(mid)

    r = await client.get(
        "/admin/media", params={"page_size": 100}, headers=_auth(token)
    )
    assert r.status_code == 200
    assert mid in [m["id"] for m in r.json()["items"]]


async def test_get_media_theo_id(client, make_user, track_media):
    token = await _token(client, make_user)
    up = await client.post(
        "/admin/media",
        files={"file": ("g.png", png_bytes((16, 9)), "image/png")},
        headers=_auth(token),
    )
    mid = up.json()["id"]
    track_media.append(mid)
    r = await client.get(f"/admin/media/{mid}", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == mid
    assert body["width"] == 16 and body["height"] == 9


async def test_get_media_khong_ton_tai_404(client, make_user):
    token = await _token(client, make_user)
    r = await client.get("/admin/media/99999999", headers=_auth(token))
    assert r.status_code == 404


async def test_delete_media_khong_ton_tai_404(client, make_user):
    token = await _token(client, make_user)
    r = await client.delete("/admin/media/99999999", headers=_auth(token))
    assert r.status_code == 404


async def test_delete_media(client, make_user):
    token = await _token(client, make_user)
    up = await client.post(
        "/admin/media",
        files={"file": ("d.png", png_bytes(), "image/png")},
        headers=_auth(token),
    )
    mid = up.json()["id"]

    r = await client.delete(f"/admin/media/{mid}", headers=_auth(token))
    assert r.status_code == 204
    # sau khi xoá thì không còn
    assert (
        await client.get(f"/admin/media/{mid}", headers=_auth(token))
    ).status_code == 404
