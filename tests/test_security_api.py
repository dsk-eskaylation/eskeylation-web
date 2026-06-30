"""Integration test bảo mật: sanitize XSS + whitelist embed qua CMS API."""

import pytest
from httpx import AsyncClient

from app.models.enums import UserRole

pytestmark = pytest.mark.integration


async def _author_token(client: AsyncClient, make_user) -> str:
    user = await make_user(password="pw", role=UserRole.author)
    r = await client.post(
        "/auth/login", data={"username": user.email, "password": "pw"}
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_create_lam_sach_xss_trong_body(client, make_user, track_content):
    token = await _author_token(client, make_user)
    r = await client.post(
        "/admin/content",
        json={
            "type": "community",
            "title": "Bài viết",
            "summary": "tóm <script>alert(1)</script>tắt",
            "body": {"content": "<p>ok</p><script>alert(1)</script>"},
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    data = r.json()
    track_content.append(data["id"])
    assert "<script" not in data["body"]["content"]
    assert "<p>ok</p>" in data["body"]["content"]
    assert "<script" not in data["summary"]


async def test_create_chan_embed_host_la_422(client, make_user):
    token = await _author_token(client, make_user)
    r = await client.post(
        "/admin/content",
        json={
            "type": "music",
            "title": "Embed lậu",
            "body": {"artist": "X", "embed_url": "https://evil.example/x"},
        },
        headers=_auth(token),
    )
    assert r.status_code == 422


async def test_create_cho_phep_embed_youtube(client, make_user, track_content):
    token = await _author_token(client, make_user)
    r = await client.post(
        "/admin/content",
        json={
            "type": "music",
            "title": "Embed ok",
            "body": {
                "artist": "X",
                "embed_url": "https://www.youtube.com/watch?v=abc",
            },
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    track_content.append(r.json()["id"])
