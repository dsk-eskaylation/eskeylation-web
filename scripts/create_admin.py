"""Tạo (hoặc cập nhật) tài khoản ADMIN đầu tiên — chạy tay 1 lần khi setup.

Cách dùng:
    uv run python scripts/create_admin.py <email> <mat_khau>

- Email chưa có: tạo user mới role=admin.
- Email đã có: nâng role lên admin + đặt lại mật khẩu theo tham số
  (script chỉ chủ dự án chạy trực tiếp, không expose qua API).
Các tài khoản tiếp theo tạo qua endpoint POST /admin/users (chỉ admin).
"""

import asyncio
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.services.security import hash_password


async def main(email: str, password: str) -> None:
    if len(password) < 8:
        raise SystemExit("Mật khẩu phải >= 8 ký tự")
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                hashed_password=hash_password(password),
                role=UserRole.admin,
            )
            session.add(user)
            action = "Tạo mới"
        else:
            user.role = UserRole.admin
            user.hashed_password = hash_password(password)
            user.is_active = True
            action = "Cập nhật"
        await session.commit()
        print(f"{action} admin: {email} (id={user.id})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(
            "Dùng: uv run python scripts/create_admin.py <email> <mat_khau>"
        )
    asyncio.run(main(sys.argv[1], sys.argv[2]))
