"""Schema quản lý tài khoản (khu vực admin)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    # bcrypt chỉ dùng 72 byte đầu — giới hạn để không gây hiểu nhầm
    password: str = Field(min_length=8, max_length=72)
    role: UserRole = UserRole.author


class UserUpdate(BaseModel):
    """Admin duyệt/đổi quyền tài khoản — chỉ field được gửi mới thay đổi."""

    is_active: bool | None = None
    role: UserRole | None = None


class UserRead(BaseModel):
    """KHÔNG bao giờ lộ hashed_password."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
