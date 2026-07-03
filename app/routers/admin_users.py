"""Quản lý tài khoản — CHỈ admin. Không có đăng ký công khai (by design)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_role
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.users import UserCreate, UserRead
from app.services.security import hash_password

router = APIRouter(prefix="/admin/users", tags=["users"])

_admin = require_role(UserRole.admin)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_admin),
) -> UserRead:
    existing = await session.scalar(select(User.id).where(User.email == data.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email đã tồn tại"
        )
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.get("", response_model=list[UserRead])
async def list_users(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_admin),
) -> list[UserRead]:
    rows = await session.scalars(select(User).order_by(User.id))
    return [UserRead.model_validate(u) for u in rows]
