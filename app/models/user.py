from sqlalchemy import CheckConstraint, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import UserRole
from app.models.mixins import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20),
        default=UserRole.author,
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        # CHECK enum ở tầng DB vì native_enum=False lưu VARCHAR (db-review C4)
        CheckConstraint(
            "role IN ('admin', 'editor', 'author')", name="ck_users_role"
        ),
    )
