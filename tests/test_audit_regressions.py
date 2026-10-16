"""Security regressions exercised against isolated PostgreSQL and real routers."""

import bcrypt
import pytest

from app.models.enums import UserRole
from app.services.security import hash_password, verify_password
from tests.test_cms_api import _create, auth, token_for

pytestmark = pytest.mark.integration


async def test_author_list_and_count_exclude_other_drafts(
    client, make_user, track_content
):
    owner = await token_for(client, make_user, UserRole.author)
    draft = await _create(
        client,
        owner,
        track_content,
        type="music",
        title="Private",
        body={"artist": "A"},
    )
    other = await token_for(client, make_user, UserRole.author)
    assert (
        await client.get(f"/admin/content/{draft['id']}", headers=auth(other))
    ).status_code == 403
    listed = await client.get("/admin/content", headers=auth(other))
    assert listed.json()["total"] == 0
    assert listed.json()["items"] == []


async def test_published_edits_require_publisher_and_stay_valid(
    client, make_user, track_content
):
    owner = await token_for(client, make_user, UserRole.author)
    draft = await _create(
        client, owner, track_content, type="music", title="Live", body={"artist": "A"}
    )
    url = f"/admin/content/{draft['id']}"
    editor = await token_for(client, make_user, UserRole.editor)
    assert (
        await client.post(url + "/publish", headers=auth(editor))
    ).status_code == 200
    assert (
        await client.patch(url, headers=auth(owner), json={"summary": "Unreviewed"})
    ).status_code == 403
    assert (
        await client.patch(url, headers=auth(editor), json={"body": {}})
    ).status_code == 422
    public = await client.get(f"/api/music/{draft['slug']}")
    assert public.json()["body"]["artist"] == "A"
    assert public.json()["summary"] != "Unreviewed"


async def test_basic_header_cannot_bypass_cookie_csrf(client, make_user):
    await token_for(client, make_user, UserRole.author)
    response = await client.post(
        "/admin/content",
        headers={"Authorization": "Basic invalid"},
        json={"type": "music", "title": "CSRF"},
    )
    assert response.status_code == 403
    assert (
        await client.get("/auth/me", headers={"Authorization": "Basic invalid"})
    ).status_code == 401


async def test_cross_origin_login_and_register_rejected(client, make_user):
    user = await make_user()
    headers = {"Origin": "https://untrusted.example"}
    response = await client.post(
        "/auth/login",
        headers=headers,
        data={"username": user.email, "password": "secret123"},
    )
    assert response.status_code == 403
    assert "set-cookie" not in response.headers
    assert (
        await client.post("/auth/register", headers=headers, json={})
    ).status_code == 403


def test_unicode_passwords_are_not_truncated():
    first, second = "é" * 36 + "A", "é" * 36 + "B"
    hashed = hash_password(first)
    assert verify_password(first, hashed)
    assert not verify_password(second, hashed)


async def test_logout_revokes_only_current_device(client, make_user):
    user = await make_user()
    tokens = []
    for _ in range(2):
        response = await client.post(
            "/auth/login", data={"username": user.email, "password": "secret123"}
        )
        tokens.append(response.json()["access_token"])
    assert (
        await client.post("/auth/logout", headers=auth(tokens[0]))
    ).status_code == 204
    assert (await client.get("/auth/me", headers=auth(tokens[0]))).status_code == 401
    assert (await client.get("/auth/me", headers=auth(tokens[1]))).status_code == 200


async def test_legacy_bcrypt_login_upgrades_hash(client, make_user, db):
    user = await make_user()
    user.hashed_password = bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode()
    await db.commit()
    response = await client.post(
        "/auth/login", data={"username": user.email, "password": "secret123"}
    )
    assert response.status_code == 200
    await db.refresh(user)
    assert user.hashed_password.startswith("$argon2id$")


async def test_member_can_authenticate_but_cannot_access_cms(client, make_user):
    token = await token_for(client, make_user, UserRole.member)
    assert (await client.get("/auth/me", headers=auth(token))).status_code == 200
    assert (await client.get("/admin/content", headers=auth(token))).status_code == 403
    assert (
        await client.post(
            "/admin/content", headers=auth(token), json={"type": "music", "title": "x"}
        )
    ).status_code == 403
