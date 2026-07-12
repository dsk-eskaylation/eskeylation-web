"""Test tích hợp tương tác cộng đồng: cảm xúc, bình luận, lưu bài (chạy thật).

Dùng Bearer token (bỏ qua CSRF vì auth qua header, không phải cookie).
Xoá content ở teardown -> cascade xoá reactions/comments/saved (ondelete CASCADE).
"""

import pytest
from httpx import AsyncClient

from app.models.enums import ContentStatus, ContentType, UserRole

pytestmark = pytest.mark.integration


async def token_for(client: AsyncClient, make_user, role: UserRole = UserRole.author):
    user = await make_user(password="pw", role=role)
    r = await client.post("/auth/login", data={"username": user.email, "password": "pw"})
    return user, r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_reaction_set_doi_va_go(client, make_user, make_content):
    _, token = await token_for(client, make_user)
    post = await make_content(type_=ContentType.community, title="Bài A")

    r = await client.put(
        f"/api/community/{post.id}/reaction", json={"type": "like"}, headers=auth(token)
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["counts"].get("like") == 1
    assert data["total"] == 1
    assert data["my_reaction"] == "like"

    # Đổi sang love -> vẫn 1 reaction của user (không cộng dồn)
    r = await client.put(
        f"/api/community/{post.id}/reaction", json={"type": "love"}, headers=auth(token)
    )
    assert r.json()["counts"].get("love") == 1
    assert r.json()["total"] == 1
    assert "like" not in r.json()["counts"]

    # Gỡ reaction
    r = await client.delete(f"/api/community/{post.id}/reaction", headers=auth(token))
    assert r.json()["total"] == 0
    assert r.json()["my_reaction"] is None


async def test_reaction_can_dang_nhap(client, make_content):
    post = await make_content(type_=ContentType.community, title="Bài B")
    r = await client.put(f"/api/community/{post.id}/reaction", json={"type": "like"})
    assert r.status_code == 401


async def test_comment_tao_va_liet_ke(client, make_user, make_content):
    user, token = await token_for(client, make_user)
    post = await make_content(type_=ContentType.community, title="Bài C")

    r = await client.post(
        f"/api/community/{post.id}/comments",
        json={"body": "Xin chào <script>alert(1)</script>"},
        headers=auth(token),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert "<script>" not in data["body"]  # đã sanitize
    assert data["author_name"] == user.email.split("@", 1)[0]

    r = await client.get(f"/api/community/{post.id}/comments")
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["id"] == data["id"]


async def test_save_va_interactions(client, make_user, make_content):
    _, token = await token_for(client, make_user)
    post = await make_content(type_=ContentType.community, title="Bài D")

    r = await client.put(f"/api/community/{post.id}/save", headers=auth(token))
    assert r.json()["saved"] is True

    r = await client.get(f"/api/community/{post.id}/interactions", headers=auth(token))
    assert r.json()["saved"] is True

    r = await client.delete(f"/api/community/{post.id}/save", headers=auth(token))
    assert r.json()["saved"] is False


async def test_tuong_tac_bai_khong_phai_community_404(client, make_user, make_content):
    _, token = await token_for(client, make_user)
    music = await make_content(type_=ContentType.music, title="Nhạc")
    r = await client.put(
        f"/api/community/{music.id}/reaction", json={"type": "like"}, headers=auth(token)
    )
    assert r.status_code == 404


async def test_tuong_tac_bai_draft_404(client, make_user, make_content):
    _, token = await token_for(client, make_user)
    draft = await make_content(
        type_=ContentType.community,
        status=ContentStatus.draft,
        title="Nháp",
        published=False,
    )
    r = await client.post(
        f"/api/community/{draft.id}/comments", json={"body": "hi"}, headers=auth(token)
    )
    assert r.status_code == 404
