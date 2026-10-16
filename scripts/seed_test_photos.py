"""Seed ảnh TEST cho trang thư viện Ảnh (gallery).

    PYTHONPATH=. PYTHONIOENCODING=utf-8 uv run python scripts/seed_test_photos.py

Cần các file media/qatest-qa*.jpg (tải bằng curl từ picsum trước đó).
Tạo 2 bài gallery published + Media rows + content_media links.
Idempotent: bỏ qua nếu slug đã tồn tại.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.db import SessionLocal
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType
from app.models.media import ContentMedia, Media

# (filename, width, height, caption)
IMAGES = [
    ("qatest-qa1.jpg", 600, 800, "Hậu trường buổi chụp"),
    ("qatest-qa2.jpg", 700, 500, "Trên sân khấu"),
    ("qatest-qa3.jpg", 640, 640, "Chân dung"),
    ("qatest-qa4.jpg", 500, 750, "Ánh đèn đêm"),
    ("qatest-qa5.jpg", 800, 600, "Khán giả"),
    ("qatest-qa6.jpg", 600, 900, "Khoảnh khắc"),
    ("qatest-qa7.jpg", 720, 480, "Ekip"),
    ("qatest-qa8.jpg", 560, 700, "Phòng thu"),
    ("qatest-qa9.jpg", 680, 520, "Đường phố"),
]

# Chia 9 ảnh thành 2 album gallery
ALBUMS = [
    ("Album ra mắt", "test-album-ra-mat", IMAGES[:5]),
    ("Hậu trường", "test-hau-truong-anh", IMAGES[5:]),
]


async def _get_or_create_media(session, fname, w, h) -> Media:
    m = await session.scalar(select(Media).where(Media.storage_key == fname))
    if m:
        return m
    m = Media(
        storage_key=fname,
        mime_type="image/jpeg",
        size=0,
        width=w,
        height=h,
        alt_text=None,
    )
    session.add(m)
    await session.flush()
    return m


async def main() -> None:
    async with SessionLocal() as session:
        for title, slug, imgs in ALBUMS:
            exists = await session.scalar(
                select(Content).where(
                    Content.type == ContentType.gallery, Content.slug == slug
                )
            )
            if exists:
                print(f"  bỏ qua (đã có): gallery/{slug}")
                continue
            content = Content(
                type=ContentType.gallery,
                status=ContentStatus.published,
                title=title,
                slug=slug,
                summary=None,
                body={"author": "Eskaylation"},
                published_at=datetime.now(UTC),
            )
            session.add(content)
            await session.flush()
            for pos, (fname, w, h, cap) in enumerate(imgs):
                media = await _get_or_create_media(session, fname, w, h)
                session.add(
                    ContentMedia(
                        content_id=content.id,
                        media_id=media.id,
                        caption=cap,
                        position=pos,
                        is_primary=(pos == 0),
                    )
                )
            print(f"  + gallery/{slug} ({len(imgs)} ảnh)")
        await session.commit()
    print("Xong.")


if __name__ == "__main__":
    asyncio.run(main())
