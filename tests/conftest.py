"""Fixtures dùng chung cho test tích hợp (chạy thật trên Supabase qua .env).

Mỗi factory tự dọn dữ liệu đã tạo sau test để DB không bị rác.
"""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.main import app
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType, UserRole
from app.models.media import ContentMedia, Media
from app.models.user import User


def unique_slug(prefix: str = "pytest") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def make_content(
    db,
) -> AsyncIterator[Callable[..., Awaitable[Content]]]:
    created: list[int] = []

    async def _make(
        *,
        type_: ContentType = ContentType.music,
        status: ContentStatus = ContentStatus.published,
        title: str = "Tiêu đề test",
        slug: str | None = None,
        summary: str | None = None,
        body: dict | None = None,
        published: bool = True,
    ) -> Content:
        content = Content(
            type=type_,
            status=status,
            title=title,
            slug=slug or unique_slug(),
            summary=summary,
            body=body or {},
            published_at=datetime.now(UTC) if published else None,
        )
        db.add(content)
        await db.commit()
        await db.refresh(content)
        created.append(content.id)
        return content

    yield _make

    if created:
        await db.execute(delete(Content).where(Content.id.in_(created)))
        await db.commit()


@pytest_asyncio.fixture
async def make_media(db) -> AsyncIterator[Callable[..., Awaitable[Media]]]:
    created: list[int] = []

    async def _make(**kwargs) -> Media:
        kwargs.setdefault("storage_key", unique_slug("media") + ".jpg")
        kwargs.setdefault("mime_type", "image/jpeg")
        kwargs.setdefault("size", 1024)
        media = Media(**kwargs)
        db.add(media)
        await db.commit()
        await db.refresh(media)
        created.append(media.id)
        return media

    yield _make

    if created:
        await db.execute(delete(Media).where(Media.id.in_(created)))
        await db.commit()


@pytest_asyncio.fixture
async def link_media(db) -> Callable[..., Awaitable[ContentMedia]]:
    async def _link(content: Content, media: Media, **kwargs) -> ContentMedia:
        link = ContentMedia(content_id=content.id, media_id=media.id, **kwargs)
        db.add(link)
        await db.commit()
        return link

    return _link


@pytest_asyncio.fixture
async def make_user(db) -> AsyncIterator[Callable[..., Awaitable[User]]]:
    from app.services.security import hash_password

    created: list[int] = []

    async def _make(
        *,
        email: str | None = None,
        password: str = "secret123",
        role: UserRole = UserRole.author,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email or f"{unique_slug('user')}@test.dev",
            hashed_password=hash_password(password),
            role=role,
            is_active=is_active,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        created.append(user.id)
        return user

    yield _make

    if created:
        await db.execute(delete(User).where(User.id.in_(created)))
        await db.commit()
