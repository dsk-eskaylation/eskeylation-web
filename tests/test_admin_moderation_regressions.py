"""Admin moderation must update open conversations and preserve role boundaries."""

from unittest.mock import AsyncMock

from app.models.enums import ContentType, UserRole
from app.routers import admin_moderation
from tests.test_cms_api import auth, token_for


async def test_admin_deletion_broadcasts_and_non_admin_cannot_delete(
    client, make_user, make_content, monkeypatch
):
    post = await make_content(type_=ContentType.community)
    member = await token_for(client, make_user, UserRole.member)
    response = await client.post(
        f"/api/community/{post.id}/comments",
        headers=auth(member),
        json={"body": "hello"},
    )
    assert response.status_code == 201
    comment_id = response.json()["id"]
    admin = await token_for(client, make_user, UserRole.admin)
    publish = AsyncMock()
    monkeypatch.setattr(admin_moderation.realtime, "publish", publish)
    url = f"/admin/moderation/comments/{comment_id}"
    assert (await client.delete(url, headers=auth(member))).status_code == 403
    publish.assert_not_awaited()
    assert (await client.delete(url, headers=auth(admin))).status_code == 204
    publish.assert_awaited_once_with(
        post.id, {"kind": "comment_delete", "comment_id": comment_id}
    )
    page = (await client.get(f"/api/community/{post.id}/comments")).json()
    assert page["total"] == 0
