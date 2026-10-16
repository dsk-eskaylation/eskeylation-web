from collections.abc import Callable, Coroutine, Sequence
from datetime import UTC, datetime
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.enums import UserRole
from app.models.session import UserSession
from app.models.user import User
from app.services.security import decode_token

# Cookie phiên đăng nhập (httpOnly) — JS không đọc được, chống trộm token qua XSS.
SESSION_COOKIE = "esk_session"
# Cookie CSRF (KHÔNG httpOnly) — frontend đọc và gửi lại qua header X-CSRF-Token.
CSRF_COOKIE = "esk_csrf"

# auto_error=False để fallback sang cookie khi không có Authorization header.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


class PaginationParams:
    """Tham số phân trang dùng chung cho mọi endpoint list."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Trang, bắt đầu từ 1"),
        page_size: int = Query(20, ge=1, le=100, description="Số mục mỗi trang"),
    ) -> None:
        self.page = page
        self.page_size = page_size


_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Không xác thực được",
    headers={"WWW-Authenticate": "Bearer"},
)


async def _session_user(payload: dict, session: AsyncSession) -> User | None:
    user_id = int(payload["sub"])
    session_id = payload["jti"]
    if not isinstance(session_id, str) or len(session_id) != 36:
        return None
    return await session.scalar(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            User.id == user_id,
            User.is_active.is_(True),
            UserSession.id == session_id,
            UserSession.expires_at > datetime.now(UTC),
        )
    )


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    # Ưu tiên Authorization header (API client/test), fallback cookie httpOnly (SPA).
    if "authorization" in request.headers and not token:
        raise _credentials_error
    token = token or request.cookies.get(SESSION_COOKIE)
    if not token:
        raise _credentials_error
    try:
        payload = decode_token(token)
        user = await _session_user(payload, session)
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
        raise _credentials_error from exc

    if user is None:
        raise _credentials_error
    return user


async def get_current_user_optional(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Như get_current_user nhưng KHÔNG ném lỗi khi thiếu/hỏng token —
    dùng cho endpoint công khai muốn biết thêm trạng thái của user hiện tại
    (vd cảm xúc/đã lưu của họ) mà vẫn cho khách xem."""
    if "authorization" in request.headers and not token:
        return None
    token = token or request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        payload = decode_token(token)
        user = await _session_user(payload, session)
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
    if user is None:
        return None
    return user


def require_role(
    *roles: UserRole,
) -> Callable[..., Coroutine[Any, Any, User]]:
    """Dependency phân quyền: chỉ cho qua nếu user có một trong các role."""

    allowed: Sequence[UserRole] = roles

    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không đủ quyền",
            )
        return user

    return checker
