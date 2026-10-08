"""Test tích hợp xác thực & phân quyền (login, JWT, RBAC)."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user, require_role
from app.models.enums import UserRole
from app.models.user import User
from app.routers import auth

pytestmark = pytest.mark.integration

# App phụ: tái dùng router login thật + thêm route được bảo vệ để test RBAC.
auth_app = FastAPI()
auth_app.include_router(auth.router)


@auth_app.get("/me")
async def _me(user: User = Depends(get_current_user)) -> dict:
    return {"id": user.id, "role": user.role.value}


@auth_app.get("/admin-only")
async def _admin_only(
    user: User = Depends(require_role(UserRole.admin)),
) -> dict:
    return {"ok": True}


@pytest_asyncio.fixture
async def aclient() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(aclient: AsyncClient, email: str, password: str):
    return await aclient.post(
        "/auth/login", data={"username": email, "password": password}
    )


# ---------- login ----------


async def test_login_thanh_cong_tra_token(aclient, make_user):
    user = await make_user(password="dung-mat-khau")
    r = await _login(aclient, user.email, "dung-mat-khau")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_sai_mat_khau_401(aclient, make_user):
    user = await make_user(password="dung")
    r = await _login(aclient, user.email, "sai")
    assert r.status_code == 401


async def test_login_email_khong_ton_tai_401(aclient):
    r = await _login(aclient, "khong-ton-tai@test.dev", "x")
    assert r.status_code == 401


async def test_login_user_bi_khoa_403(aclient, make_user):
    user = await make_user(password="pw", is_active=False)
    r = await _login(aclient, user.email, "pw")
    assert r.status_code == 403


# ---------- get_current_user ----------


async def test_me_voi_token_hop_le(aclient, make_user):
    user = await make_user(password="pw", role=UserRole.editor)
    token = (await _login(aclient, user.email, "pw")).json()["access_token"]
    r = await aclient.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"id": user.id, "role": "editor"}


async def test_me_khong_co_token_401(aclient):
    assert (await aclient.get("/me")).status_code == 401


async def test_me_token_sai_401(aclient):
    r = await aclient.get("/me", headers={"Authorization": "Bearer khong-hop-le"})
    assert r.status_code == 401


# ---------- RBAC ----------


async def test_require_role_dung_quyen(aclient, make_user):
    admin = await make_user(password="pw", role=UserRole.admin)
    token = (await _login(aclient, admin.email, "pw")).json()["access_token"]
    r = await aclient.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_require_role_sai_quyen_403(aclient, make_user):
    author = await make_user(password="pw", role=UserRole.author)
    token = (await _login(aclient, author.email, "pw")).json()["access_token"]
    r = await aclient.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
