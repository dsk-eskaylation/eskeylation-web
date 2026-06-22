from collections.abc import Sequence

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.enums import UserRole
from app.models.user import User
from app.services.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

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
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _credentials_error

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise _credentials_error
    return user


def require_role(*roles: UserRole):
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
