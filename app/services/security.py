from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

settings = get_settings()
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def _encode(password: str) -> bytes:
    # Chỉ đọc hash bcrypt cũ; hash mới giữ toàn bộ mật khẩu bằng Argon2id.
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    if len(password) > 1024:
        return False
    try:
        if hashed.startswith(("$2a$", "$2b$", "$2y$")):
            return bcrypt.checkpw(_encode(password), hashed.encode("utf-8"))
        return _hasher.verify(hashed, password)
    except (ValueError, VerificationError, InvalidHashError):
        return False


def verify_and_upgrade(password: str, hashed: str) -> tuple[bool, str | None]:
    if not verify_password(password, hashed):
        return False, None
    upgrade = not hashed.startswith("$argon2id$") or _hasher.check_needs_rehash(hashed)
    return True, hash_password(password) if upgrade else None


def create_access_token(subject: str, session_id: str | None = None) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, "jti": session_id or str(uuid4())}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp", "jti"]},
    )
