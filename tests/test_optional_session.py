"""Anonymous public browsing is not an authentication error."""

from app.models.enums import UserRole
from tests.test_cms_api import auth, token_for


async def test_anonymous_session_is_null_without_relaxing_protected_auth(client):
    response = await client.get("/auth/session")
    assert response.status_code == 200
    assert response.json() is None
    assert response.headers["cache-control"] == "no-store"
    assert (await client.get("/auth/me")).status_code == 401


async def test_session_returns_public_user_fields_and_respects_revocation(
    client, make_user
):
    token = await token_for(client, make_user, UserRole.admin)
    response = await client.get("/auth/session", headers=auth(token))
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert "password" not in response.text
    await client.post("/auth/logout", headers=auth(token))
    assert (await client.get("/auth/session", headers=auth(token))).json() is None


async def test_invalid_authorization_does_not_fall_back_to_cookie(client, make_user):
    await token_for(client, make_user, UserRole.admin)
    response = await client.get(
        "/auth/session", headers={"Authorization": "Basic invalid"}
    )
    assert response.status_code == 200
    assert response.json() is None
