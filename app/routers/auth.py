from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import get_current_user
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.users import UserCreate, UserRead
from app.services.ratelimit import check_rate
from app.services.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash mồi cho email không tồn tại: luôn tốn 1 lần bcrypt như email đúng,
# tránh dò user qua chênh lệch thời gian phản hồi (timing attack).
_DUMMY_HASH = hash_password("dummy-timing-guard")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Token:
    # Chống brute-force: giới hạn theo (IP, email) và tổng theo IP
    ip = _client_ip(request)
    check_rate(f"login:{ip}:{form.username}", limit=5)
    check_rate(f"login-ip:{ip}", limit=60)

    result = await session.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    hashed = user.hashed_password if user else _DUMMY_HASH
    if not verify_password(form.password, hashed) or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản bị khoá"
        )
    return Token(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> UserRead:
    """Thông tin tài khoản đang đăng nhập — để frontend biết vai trò."""
    return UserRead.model_validate(user)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    data: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Đăng ký công khai: tài khoản tạo ra ở trạng thái CHỜ DUYỆT
    (is_active=False, role=author). Admin kích hoạt qua PATCH /admin/users/{id}.
    Không cho tự chọn role — chống leo quyền."""
    ip = _client_ip(request)
    check_rate(f"register:{ip}", limit=10, window_seconds=300)

    existing = await session.scalar(select(User.id).where(User.email == data.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email đã tồn tại"
        )
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.author,  # cố định — bỏ qua data.role nếu client gửi
        is_active=False,  # chờ admin duyệt
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)
