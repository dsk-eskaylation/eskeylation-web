"""Regression checks for cookie-authenticated social routes and private data."""

import pytest
from sqlalchemy import select

from app.models.enums import ContentType, UserRole
from app.models.media import Media
from tests.test_community_api import auth, token_for


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/api/me/posts", None),
        ("GET", "/api/me/saved", None),
        ("GET", "/api/me/notifications", None),
        ("POST", "/api/me/notifications/read", None),
        ("POST", "/api/community/posts", {"summary": "review"}),
        ("POST", "/api/community/uploads", None),
        ("PATCH", "/auth/me", {"bio": "review"}),
    ],
)
async def test_new_routes_require_login(client, method, path, payload):
    r = await client.request(method, path, json=payload)
    assert r.status_code == 401, r.text


async def test_private_lists_and_read_notifications_are_owner_scoped(
    client, db, make_user, make_content
):
    owner, owner_token = await token_for(client, make_user, UserRole.member)
    _, other_token = await token_for(client, make_user, UserRole.member)
    post = await make_content(type_=ContentType.community)
    post.author_id = owner.id
    await db.commit()
    await client.put(
        f"/api/community/{post.id}/reaction",
        json={"type": "like"},
        headers=auth(other_token),
    )
    await client.put(f"/api/community/{post.id}/save", headers=auth(owner_token))
    assert (
        await client.get("/api/me/notifications", headers=auth(other_token))
    ).json()["items"] == []
    await client.post("/api/me/notifications/read", headers=auth(other_token))
    assert (
        await client.get("/api/me/notifications", headers=auth(owner_token))
    ).json()["unread"] == 1
    assert (await client.get("/api/me/posts", headers=auth(other_token))).json()[
        "items"
    ] == []
    assert (await client.get("/api/me/saved", headers=auth(other_token))).json()[
        "total"
    ] == 0


@pytest.mark.parametrize(
    "path,method,data",
    [
        ("/auth/me", "PATCH", {"bio": "x"}),
        ("/api/community/posts", "POST", {"summary": "x"}),
        ("/api/community/uploads", "POST", None),
        ("/api/me/notifications/read", "POST", None),
    ],
)
async def test_new_mutations_enforce_cookie_csrf(client, make_user, path, method, data):
    await token_for(client, make_user, UserRole.member)
    r = await client.request(method, path, json=data)
    assert r.status_code == 403, (path, r.text)
    wrong = await client.request(
        method, path, json=data, headers={"X-CSRF-Token": "wrong"}
    )
    assert wrong.status_code == 403
    if path in {"/auth/me", "/api/me/notifications/read"}:
        accepted = await client.request(
            method,
            path,
            json=data,
            headers={"X-CSRF-Token": client.cookies["esk_csrf"]},
        )
        assert accepted.status_code == (200 if method == "PATCH" else 204)


async def test_member_image_upload_is_throttled_and_does_not_create_more_media(
    client, db, make_user, monkeypatch
):
    from fastapi import HTTPException

    from app.routers import community as router

    calls = []

    async def blocked(key, **kwargs):
        calls.append((key, kwargs))
        raise HTTPException(429, "review limit")

    member, token = await token_for(client, make_user, UserRole.member)
    monkeypatch.setattr(router, "check_rate", blocked)
    r = await client.post(
        "/api/community/uploads", content=b"not multipart", headers=auth(token)
    )
    assert r.status_code == 429
    assert calls == [(f"post-upload:{member.id}", {"limit": 30, "window_seconds": 600})]
    assert (
        await db.scalars(select(Media).where(Media.uploaded_by == member.id))
    ).all() == []


@pytest.mark.parametrize("size", [0, 100, 101, 201])
async def test_authored_posts_paging_and_ownership(
    client, db, make_user, track_content, size
):
    from app.models.content import Content
    from app.models.enums import ContentStatus

    owner, token = await token_for(client, make_user, UserRole.member)
    other = await make_user()
    records = [
        Content(
            type=ContentType.community,
            title=f"Fixture {i}",
            slug=f"page-{owner.id}-{i}",
            author_id=owner.id,
            status=ContentStatus.draft,
            body={},
        )
        for i in range(size)
    ]
    records += [
        Content(
            type=ContentType.community,
            title="Other user",
            slug=f"other-{owner.id}",
            author_id=other.id,
            status=ContentStatus.draft,
            body={},
        ),
        Content(
            type=ContentType.community,
            title="Archived",
            slug=f"archived-{owner.id}",
            author_id=owner.id,
            status=ContentStatus.archived,
            body={},
        ),
    ]
    db.add_all(records)
    await db.commit()
    track_content.extend(c.id for c in records)
    found = []
    for page in range(1, (size + 99) // 100 + 2):
        r = await client.get(
            f"/api/me/posts?page={page}&page_size=100", headers=auth(token)
        )
        assert r.status_code == 200, r.text
        result = r.json()
        assert result["total"] == size
        assert len(result["items"]) <= 100
        assert all(c["body"]["review_status"] == "draft" for c in result["items"])
        found.extend(c["id"] for c in result["items"])
    assert len(found) == size and len(set(found)) == size
    assert found == sorted((c.id for c in records[:size]), reverse=True)
