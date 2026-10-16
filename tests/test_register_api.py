"""Test tích hợp đăng ký công khai + duyệt tài khoản + rate limit."""

import pytest
from sqlalchemy import delete, select

from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import unique_slug
from tests.test_cms_api import auth, token_for

pytestmark = pytest.mark.integration


async def _cleanup(db, email: str) -> None:
    await db.execute(delete(User).where(User.email == email))
    await db.commit()


async def test_register_tao_tai_khoan_cho_duyet(client, db, make_user):
    email = f"{unique_slug('reg')}@test.dev"
    try:
        r = await client.post(
            "/auth/register", json={"email": email, "password": "matkhau-8kytu"}
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["is_active"] is False  # chờ duyệt
        assert data["role"] == "author"
        assert "password" not in data and "hashed_password" not in data

        # Chưa duyệt -> login bị chặn 403 (tài khoản khoá)
        r = await client.post(
            "/auth/login", data={"username": email, "password": "matkhau-8kytu"}
        )
        assert r.status_code == 403

        # Admin duyệt qua PATCH -> login được
        admin_token = await token_for(client, make_user, UserRole.admin)
        r = await client.patch(
            f"/admin/users/{data['id']}",
            json={"is_active": True},
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["is_active"] is True

        r = await client.post(
            "/auth/login", data={"username": email, "password": "matkhau-8kytu"}
        )
        assert r.status_code == 200
        assert r.json()["access_token"]
    finally:
        await _cleanup(db, email)


async def test_register_khong_the_tu_chon_role_admin(client, db):
    # Client cố leo quyền bằng cách gửi role=admin -> server ép về author
    email = f"{unique_slug('esc')}@test.dev"
    try:
        r = await client.post(
            "/auth/register",
            json={"email": email, "password": "matkhau-8kytu", "role": "admin"},
        )
        assert r.status_code == 201
        assert r.json()["role"] == "author"
        role_in_db = await db.scalar(select(User.role).where(User.email == email))
        assert role_in_db == UserRole.author
    finally:
        await _cleanup(db, email)


async def test_register_email_trung_409(client, make_user):
    existing = await make_user(password="pw12345678")
    r = await client.post(
        "/auth/register",
        json={"email": existing.email, "password": "matkhau-8kytu"},
    )
    assert r.status_code == 409


async def test_login_rate_limit_theo_email(client):
    # 5 lần sai cùng 1 email -> lần 6 bị 429 (chống brute-force)
    email = f"{unique_slug('brute')}@test.dev"
    for _ in range(5):
        r = await client.post(
            "/auth/login", data={"username": email, "password": "sai-mat-khau"}
        )
        assert r.status_code == 401
    r = await client.post(
        "/auth/login", data={"username": email, "password": "sai-mat-khau"}
    )
    assert r.status_code == 429


async def test_admin_khong_the_tu_khoa_minh(client, make_user):
    admin = await make_user(password="pw12345678", role=UserRole.admin)
    r = await client.post(
        "/auth/login", data={"username": admin.email, "password": "pw12345678"}
    )
    token = r.json()["access_token"]
    r = await client.patch(
        f"/admin/users/{admin.id}",
        json={"is_active": False},
        headers=auth(token),
    )
    assert r.status_code == 422
    r = await client.patch(
        f"/admin/users/{admin.id}",
        json={"role": "author"},
        headers=auth(token),
    )
    assert r.status_code == 422


async def test_me_tra_vai_tro(client, make_user):
    token = await token_for(client, make_user, UserRole.editor)
    r = await client.get("/auth/me", headers=auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "editor"
    assert "hashed_password" not in data


async def test_me_khong_token_401(client):
    r = await client.get("/auth/me")
    assert r.status_code == 401


async def test_security_headers_co_mat(client):
    r = await client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert "referrer-policy" in r.headers
