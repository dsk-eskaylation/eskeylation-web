import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.routers import auth, public

settings = get_settings()

logging.basicConfig(
    level=logging.INFO if settings.environment == "prod" else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="Eskaylation API",
    version="0.1.0",
    description="API công khai và quản trị cho kho lưu trữ số DSK.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(public.router)


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
