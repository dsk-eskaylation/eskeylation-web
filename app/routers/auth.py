import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db import get_session
from app.dependencies import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    get_current_user,
    get_current_user_optional,
)
from app.models.enums import UserRole
from app.models.session import UserSession
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.users import ProfileUpdate, UserCreate, UserRead
from app.services import moderation
from app.services.ratelimit import check_rate
from app.services.sanitize import sanitize_summary
from app.services.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_and_upgrade,
)

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash mồi cho email không tồn tại: vẫn xác minh Argon2 như email đúng,
# tránh dò user qua chênh lệch thời gian phản hồi (timing attack).
_DUMMY_HASH = hash_password("dummy-timing-guard")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_session_cookies(response: Response, token: str) -> None:
    """Phiên đăng nhập qua cookie httpOnly (JS không đọc được — chống XSS trộm
    token) + cookie CSRF double-submit cho SPA."""
    max_age = settings.access_token_expire_minutes * 60
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=settings.is_prod,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(32),
        max_age=max_age,
        httponly=False,  # frontend phải đọc được để gửi X-CSRF-Token
        samesite="lax",
        secure=settings.is_prod,
        path="/",
    )


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Token:
    # Bound attacker-controlled rate-limit keys and avoid hashing impossible
    # credentials. The DB email column is 255 characters; legacy passwords
    # already reject values longer than 1024 in verify_password().
    if len(form.username) > 255 or len(form.password) > 1024:
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    # Chống brute-force: giới hạn theo (IP, email) và tổng theo IP
    ip = _client_ip(request)
    await check_rate(f"login-ip:{ip}", limit=60)
    await check_rate(f"login:{ip}:{form.username}", limit=5)

    # Serialize issuing a session with admin lock/revocation on this user.
    result = await session.execute(
        select(User).where(User.email == form.username).with_for_update()
    )
    user = result.scalar_one_or_none()
    hashed = user.hashed_password if user else _DUMMY_HASH
    valid, upgraded = await run_in_threadpool(verify_and_upgrade, form.password, hashed)
    if not valid or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản bị khoá"
        )
    if upgraded:
        user.hashed_password = upgraded
    session_id = str(uuid4())
    now = datetime.now(UTC)
    await session.execute(
        delete(UserSession).where(
            UserSession.user_id == user.id, UserSession.expires_at <= now
        )
    )
    session.add(
        UserSession(
            id=session_id,
            user_id=user.id,
            expires_at=now + timedelta(minutes=settings.access_token_expire_minutes),
        )
    )
    await session.commit()
    token = create_access_token(str(user.id), session_id)
    _set_session_cookies(response, token)
    # Vẫn trả token trong body cho API client/tool dùng Authorization header.
    return Token(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Thu hồi đúng phiên hiện tại; các thiết bị khác vẫn đăng nhập."""
    authorization = request.headers.get("authorization", "").split()
    token = (
        authorization[1]
        if len(authorization) == 2 and authorization[0].lower() == "bearer"
        else request.cookies.get(SESSION_COOKIE)
    )
    if token:
        try:
            payload = decode_token(token)
            await session.execute(
                delete(UserSession).where(
                    UserSession.id == payload["jti"],
                    UserSession.user_id == int(payload["sub"]),
                )
            )
            await session.commit()
        except (jwt.PyJWTError, KeyError, ValueError, TypeError):
            pass
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> UserRead:
    """Thông tin tài khoản đang đăng nhập — để frontend biết vai trò."""
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
async def update_me(
    data: ProfileUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    bio = sanitize_summary(data.bio or "") or ""
    await moderation.assert_clean(session, text=bio)
    user.bio = bio.strip() or None
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.get("/session")
async def session_info(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> UserRead | None:
    """Phiên tùy chọn cho trang public; khách chưa đăng nhập không phải lỗi API."""
    return UserRead.model_validate(user) if user else None


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    data: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Đăng ký công khai: tài khoản tạo ra ở trạng thái CHỜ DUYỆT
    (is_active=False, role=member). Admin kích hoạt qua PATCH /admin/users/{id}.
    Không cho tự chọn role — chống leo quyền."""
    ip = _client_ip(request)
    await check_rate(f"register:{ip}", limit=10, window_seconds=300)

    existing = await session.scalar(select(User.id).where(User.email == data.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email đã tồn tại"
        )
    user = User(
        email=data.email,
        hashed_password=await run_in_threadpool(hash_password, data.password),
        role=UserRole.member,  # người dùng cộng đồng không có quyền biên tập
        is_active=False,  # chờ admin duyệt
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        # Hai request đăng ký cùng email đua nhau qua bước check
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email đã tồn tại"
        ) from exc
    await session.refresh(user)
    return UserRead.model_validate(user)
