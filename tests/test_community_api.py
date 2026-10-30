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
    r = await client.post(
        "/auth/login", data={"username": user.email, "password": "pw"}
    )
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
    video = await make_content(type_=ContentType.video, title="Video")
    r = await client.put(
        f"/api/community/{video.id}/reaction",
        json={"type": "like"},
        headers=auth(token),
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


async def test_bai_nhac_duoc_yeu_thich_va_binh_luan(client, make_user, make_content):
    _, token = await token_for(client, make_user)
    music = await make_content(type_=ContentType.music, title="Nhạc")
    base = f"/api/community/{music.id}"
    assert (await client.put(f"{base}/save", headers=auth(token))).status_code == 200
    created = await client.post(
        f"{base}/comments", json={"body": "Hay quá"}, headers=auth(token)
    )
    assert created.status_code == 201, created.text
    overview = (await client.get(f"{base}/interactions", headers=auth(token))).json()
    assert overview["saved"] is True and overview["comment_count"] == 1


async def test_danh_sach_da_luu_va_yeu_thich(client, make_user, make_content):
    _, token = await token_for(client, make_user)
    post = await make_content(type_=ContentType.community, title="Bài lưu")
    song = await make_content(type_=ContentType.music, title="Bài thích")
    for item in (post, song):
        await client.put(f"/api/community/{item.id}/save", headers=auth(token))
    saved = await client.get("/api/me/saved", headers=auth(token))
    favorites = await client.get("/api/me/saved?type=music", headers=auth(token))
    assert [c["id"] for c in saved.json()["items"]] == [post.id]
    assert [c["id"] for c in favorites.json()["items"]] == [song.id]
    client.cookies.clear()  # login set a session cookie
    assert (await client.get("/api/me/saved")).status_code == 401


async def test_cap_nhat_bio(client, make_user):
    _, token = await token_for(client, make_user)
    r = await client.patch("/auth/me", json={"bio": "  Fan DSK  "}, headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["bio"] == "Fan DSK"


async def test_thanh_vien_gui_bai_cho_duyet_va_tu_cam_duoc_bao(client, db, make_user):
    from sqlalchemy import select

    from app.models.activity import ActivityLog
    from app.models.content import Content
    from app.models.moderation import BannedWord
    from app.services import moderation

    _, token = await token_for(client, make_user, UserRole.member)
    r = await client.post(
        "/api/community/posts",
        json={"title": "Kỷ niệm", "summary": "Lần đầu nghe DSK"},
        headers=auth(token),
    )
    assert r.status_code == 201, r.text
    post = await db.scalar(select(Content).where(Content.title == "Kỷ niệm"))
    assert post.status == ContentStatus.draft and post.body["author"]

    db.add(BannedWord(word="tukhoacam"))
    await db.commit()
    moderation.invalidate()
    blocked = await client.post(
        "/api/community/posts",
        json={"title": "Bài xấu", "summary": "có tukhoacam"},
        headers=auth(token),
    )
    assert blocked.status_code == 422
    assert blocked.json()["detail"] == moderation.BLOCKED_MESSAGE
    entry = await db.scalar(
        select(ActivityLog).where(ActivityLog.action == "content_blocked")
    )
    assert entry.detail == {"words": ["tukhoacam"]}
    await db.delete(
        await db.scalar(select(BannedWord).where(BannedWord.word == "tukhoacam"))
    )
    await db.commit()
    moderation.invalidate()


async def test_thong_bao_khi_co_nguoi_tuong_tac(client, db, make_user, make_content):
    author, author_token = await token_for(client, make_user, UserRole.member)
    _, fan_token = await token_for(client, make_user, UserRole.member)
    post = await make_content(type_=ContentType.community, title="Bài của tôi")
    post.author_id = author.id
    await db.commit()
    base = f"/api/community/{post.id}"

    # Tự tương tác bài mình không tạo thông báo
    await client.put(
        f"{base}/reaction", json={"type": "like"}, headers=auth(author_token)
    )
    own = await client.post(
        f"{base}/comments", json={"body": "Của tôi"}, headers=auth(author_token)
    )
    await client.put(f"{base}/reaction", json={"type": "like"}, headers=auth(fan_token))
    await client.put(f"{base}/reaction", json={"type": "love"}, headers=auth(fan_token))
    await client.post(f"{base}/comments", json={"body": "Hay"}, headers=auth(fan_token))
    await client.put(
        f"{base}/comments/{own.json()['id']}/reaction",
        json={"type": "haha"},
        headers=auth(fan_token),
    )

    data = (
        await client.get("/api/me/notifications", headers=auth(author_token))
    ).json()
    assert data["unread"] == 3
    assert sorted(n["kind"] for n in data["items"]) == [
        "comment_reaction",
        "post_comment",
        "post_reaction",
    ]
    assert data["items"][0]["content_slug"] == post.slug
    r = await client.post("/api/me/notifications/read", headers=auth(author_token))
    assert r.status_code == 204
    again = await client.get("/api/me/notifications", headers=auth(author_token))
    assert again.json()["unread"] == 0


async def test_bai_cua_toi_gom_ca_bai_cho_duyet(client, make_user):
    _, token = await token_for(client, make_user, UserRole.member)
    await client.post(
        "/api/community/posts",
        json={"title": "Chờ duyệt", "summary": "Nội dung"},
        headers=auth(token),
    )
    mine = (await client.get("/api/me/posts", headers=auth(token))).json()["items"]
    assert [(p["title"], p["body"]["review_status"]) for p in mine] == [
        ("Chờ duyệt", "draft")
    ]


async def test_thanh_vien_dang_bai_kem_anh_cua_minh(client, db, make_user):
    from sqlalchemy import select

    from app.models.content import Content
    from tests.test_media_api import mp4_bytes, png_bytes

    member, token = await token_for(client, make_user, UserRole.member)
    _, other_token = await token_for(client, make_user, UserRole.member)

    def upload(tok, name="a.png", data=None, mime="image/png"):
        return client.post(
            "/api/community/uploads",
            files={"file": (name, data or png_bytes(), mime)},
            headers=auth(tok),
        )

    mine = (await upload(token)).json()["id"]
    theirs = (await upload(other_token)).json()["id"]
    video = await upload(token, "clip.mp4", mp4_bytes(), "video/mp4")
    assert video.status_code == 415

    stolen = await client.post(
        "/api/community/posts",
        json={"summary": "Ảnh người khác", "media_ids": [theirs]},
        headers=auth(token),
    )
    assert stolen.status_code == 422

    r = await client.post(
        "/api/community/posts",
        json={"summary": "Buổi offline\nĐông vui lắm", "media_ids": [mine]},
        headers=auth(token),
    )
    assert r.status_code == 201, r.text
    post = await db.scalar(select(Content).where(Content.author_id == member.id))
    await db.refresh(post, ["media_links"])
    assert post.title == "Buổi offline"
    assert [link.media_id for link in post.media_links] == [mine]

    reused = await client.post(
        "/api/community/posts",
        json={"summary": "Dùng lại ảnh", "media_ids": [mine]},
        headers=auth(token),
    )
    assert reused.status_code == 422
