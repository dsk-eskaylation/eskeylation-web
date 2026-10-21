"""Homepage avatars must survive editing and reference attached image assets."""

import pytest

from app.models.enums import UserRole
from tests.test_cms_api import _create, auth, token_for


async def test_homepage_member_images_round_trip_and_invalid_edit_is_atomic(
    client, make_user, make_media, track_content
):
    token = await token_for(client, make_user, UserRole.admin)
    image = await make_media(mime_type="image/png")
    body = {
        "intro": "Fake intro",
        "sections": [{"type": "intro"}],
        "leader": {"name": "Fake leader", "media_id": image.id},
        "credits": [
            {
                "role": "Design",
                "members": [{"name": "Fake member", "media_id": image.id}],
            }
        ],
    }
    content = await _create(
        client,
        token,
        track_content,
        type="homepage",
        title="Fake homepage",
        body=body,
        media=[{"media_id": image.id}],
    )
    url = f"/admin/content/{content['id']}"
    assert (await client.post(url + "/publish", headers=auth(token))).status_code == 200
    public = (await client.get("/api/homepage")).json()
    assert public["body"] == body
    assert public["media"][0]["media_id"] == image.id
    assert public["media"][0]["url"]

    invalid = await client.patch(
        url, headers=auth(token), json={"title": "Should not save", "media": []}
    )
    assert invalid.status_code == 422
    unchanged = (await client.get(url, headers=auth(token))).json()
    assert unchanged["title"] == content["title"]
    assert unchanged["body"] == body
    assert unchanged["media"][0]["media_id"] == image.id
    cleared = await client.patch(
        url,
        headers=auth(token),
        json={
            "body": {**body, "leader": None, "credits": []},
            "media": [],
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["media"] == []


@pytest.mark.parametrize("ref", [True, "1", -1, 1.5, 999999999])
async def test_homepage_rejects_unattached_or_invalid_avatar_reference(
    client, make_user, ref
):
    token = await token_for(client, make_user, UserRole.admin)
    response = await client.post(
        "/admin/content",
        headers=auth(token),
        json={
            "type": "homepage",
            "title": "Fake invalid avatar",
            "body": {
                "credits": [
                    {"role": "Fake", "members": [{"name": "Fake", "media_id": ref}]}
                ]
            },
        },
    )
    assert response.status_code == 422


async def test_homepage_rejects_non_image_avatar(client, make_user, make_media):
    token = await token_for(client, make_user, UserRole.admin)
    audio = await make_media(mime_type="audio/mpeg")
    response = await client.post(
        "/admin/content",
        headers=auth(token),
        json={
            "type": "homepage",
            "title": "Fake audio avatar",
            "body": {"leader": {"name": "Fake", "media_id": audio.id}},
            "media": [{"media_id": audio.id}],
        },
    )
    assert response.status_code == 422


async def test_legacy_homepage_names_are_preserved(client, make_user, track_content):
    token = await token_for(client, make_user, UserRole.admin)
    body = {"credits": [{"role": "Design", "names": ["Legacy one", "Legacy two"]}]}
    content = await _create(
        client, token, track_content, type="homepage", title="Fake legacy", body=body
    )
    response = await client.patch(
        f"/admin/content/{content['id']}",
        headers=auth(token),
        json={"title": "Updated metadata"},
    )
    assert response.status_code == 200
    assert response.json()["body"] == body
