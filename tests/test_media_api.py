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


async def test_get_media_khong_ton_tai_404(client, make_user):
    token = await _token(client, make_user)
    r = await client.get("/admin/media/99999999", headers=_auth(token))
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
