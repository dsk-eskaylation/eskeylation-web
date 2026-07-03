import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.routers import admin_content, admin_users, auth, media, public

settings = get_settings()

logging.basicConfig(
    level=logging.INFO if settings.environment == "prod" else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("eskaylation")

# Lưới an toàn: không cho chạy prod với secret mặc định
if settings.jwt_secret == "change-me-in-production":
    if settings.environment == "prod":
        raise RuntimeError("JWT_SECRET chưa được đặt — không được chạy prod!")
    logger.warning("JWT_SECRET đang là giá trị mặc định — chỉ chấp nhận ở dev.")

app = FastAPI(
    title="Eskaylation API",
    version="0.1.0",
    description="API công khai và quản trị cho kho lưu trữ số DSK.",
)


@app.middleware("http")
async def security_headers(request, call_next):
    """Header bảo mật cơ bản cho mọi response."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(public.router)
app.include_router(media.router)
app.include_router(admin_content.router)
app.include_router(admin_users.router)

# Phục vụ media cục bộ ở dev (production dùng Supabase Storage + CDN — Phase 9).
_media_dir = Path(settings.media_root)
_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=_media_dir), name="media")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Liveness — tiến trình còn sống."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    """Readiness — kết nối được database."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ready"}
