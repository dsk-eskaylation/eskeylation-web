import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.dependencies import CSRF_COOKIE, SESSION_COOKIE
from app.routers import (
    admin_content,
    admin_users,
    auth,
    community,
    lyrics,
    media,
    public,
)
from app.services import realtime

settings = get_settings()

logging.basicConfig(
    level=logging.INFO if settings.is_prod else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("eskaylation")

# Lưới an toàn: không cho chạy prod với secret mặc định.
# is_prod fail-safe: mọi ENVIRONMENT khác "dev" đều bị coi là prod.
if settings.jwt_secret == "change-me-in-production":
    if settings.is_prod:
        raise RuntimeError("JWT_SECRET chưa được đặt — không được chạy prod!")
    logger.warning("JWT_SECRET đang là giá trị mặc định — chỉ chấp nhận ở dev.")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Bật task lắng nghe Redis pub/sub cho realtime cộng đồng
    await realtime.start()
    try:
        yield
    finally:
        await realtime.stop()


app = FastAPI(
    title="Eskaylation API",
    version="0.1.0",
    description="API công khai và quản trị cho kho lưu trữ số DSK.",
    lifespan=lifespan,
)


# CSP: script chỉ từ chính site; style/font cho Google Fonts; ảnh cho phép https
# (thumbnail YouTube + Supabase CDN); iframe chỉ YouTube/Vimeo (khớp whitelist embed).
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob: https:; "
    "media-src 'self' https:; "
    "frame-src https://www.youtube.com https://player.vimeo.com; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'self'"
)


_MUTATING = {"POST", "PATCH", "PUT", "DELETE"}


@app.middleware("http")
async def csrf_guard(request, call_next):
    """CSRF double-submit cho phiên cookie: request mutating vào /admin hoặc
    /auth/logout mà xác thực bằng cookie (không có Authorization header) phải
    kèm X-CSRF-Token khớp cookie esk_csrf. Auth bằng header thì miễn — trình
    duyệt không tự gửi header cross-site được nên không dính CSRF."""
    if (
        request.method in _MUTATING
        and (
            request.url.path.startswith("/admin")
            or request.url.path.startswith("/api/community")
            or request.url.path.startswith("/api/music")
            or request.url.path == "/auth/logout"
        )
        and "authorization" not in request.headers
        and SESSION_COOKIE in request.cookies
    ):
        csrf_cookie = request.cookies.get(CSRF_COOKIE)
        csrf_header = request.headers.get("x-csrf-token")
        if not csrf_cookie or csrf_header != csrf_cookie:
            return JSONResponse(
                status_code=403, content={"detail": "CSRF token không hợp lệ"}
            )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request, call_next):
    """Header bảo mật cho mọi response (CSP là lớp chặn XSS/exfiltration chính)."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", _CSP)
    if settings.is_prod:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
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
app.include_router(community.router)
app.include_router(lyrics.router)
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


# ---- Co-host SPA (production): serve frontend/dist nếu đã build ----
# Same-origin với API -> cookie phiên SameSite hoạt động, không cần CORS cross-site.
# Route catch-all đăng ký CUỐI CÙNG nên mọi route API cụ thể luôn match trước.
_spa_dir = Path("frontend/dist")
if _spa_dir.is_dir():  # pragma: no cover — chỉ tồn tại sau khi build SPA
    app.mount("/assets", StaticFiles(directory=_spa_dir / "assets"), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        """File tĩnh ở gốc dist (favicon...) hoặc index.html cho route SPA."""
        file = (_spa_dir / full_path).resolve()
        # chống path traversal: chỉ serve file nằm TRONG dist
        if full_path and file.is_file() and file.is_relative_to(_spa_dir.resolve()):
            return FileResponse(file)
        return FileResponse(_spa_dir / "index.html")
