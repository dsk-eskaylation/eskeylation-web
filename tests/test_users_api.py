"""Test tích hợp quản lý tài khoản /admin/users — chỉ admin được thao tác."""

import pytest
from sqlalchemy import delete

from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import unique_slug
from tests.test_cms_api import auth, token_for

pytestmark = pytest.mark.integration


def _payload(role: str = "author") -> dict:
    return {
        "email": f"{unique_slug('newuser')}@test.dev",
        "password": "matkhau-8kytu",
        "role": role,
    }


async def test_admin_tao_user_201_khong_lo_password(client, db, make_user):
    token = await token_for(client, make_user, UserRole.admin)
    payload = _payload("editor")
    r = await client.post("/admin/users", json=payload, headers=auth(token))
    assert r.status_code == 201, r.text
    data = r.json()
    try:
        assert data["email"] == payload["email"]
        assert data["role"] == "editor"
        assert data["is_active"] is True
        # KHÔNG bao giờ trả password/hash
        assert "password" not in data and "hashed_password" not in data
    finally:
        await db.execute(delete(User).where(User.id == data["id"]))
        await db.commit()


async def test_khong_phai_admin_bi_403(client, make_user):
    for role in (UserRole.editor, UserRole.author):
        token = await token_for(client, make_user, role)
        r = await client.post("/admin/users", json=_payload(), headers=auth(token))
        assert r.status_code == 403


async def test_khong_dang_nhap_401(client):
    r = await client.post("/admin/users", json=_payload())
    assert r.status_code == 401


async def test_email_trung_409(client, make_user):
    token = await token_for(client, make_user, UserRole.admin)
    existing = await make_user(password="pw12345678")
    r = await client.post(
        "/admin/users",
        json={"email": existing.email, "password": "matkhau-8kytu"},
        headers=auth(token),
    )
    assert r.status_code == 409


async def test_mat_khau_ngan_422(client, make_user):
    token = await token_for(client, make_user, UserRole.admin)
    payload = _payload()
    payload["password"] = "ngan"
    r = await client.post("/admin/users", json=payload, headers=auth(token))
    assert r.status_code == 422


async def test_list_users_chi_admin(client, make_user):
    admin_token = await token_for(client, make_user, UserRole.admin)
    r = await client.get("/admin/users", headers=auth(admin_token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    author_token = await token_for(client, make_user, UserRole.author)
    r = await client.get("/admin/users", headers=auth(author_token))
    assert r.status_code == 403
