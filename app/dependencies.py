from collections.abc import Callable, Coroutine, Sequence
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.enums import UserRole
from app.models.user import User
from app.services.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


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


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise _credentials_error from exc

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise _credentials_error
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
