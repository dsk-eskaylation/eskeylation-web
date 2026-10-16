"""Seed dữ liệu TEST cho trang nghe nhạc / video / cộng đồng.

    uv run python scripts/seed_test_content.py

- Nhạc: body.audio_url = mp3 công khai (SoundHelix) để <audio> phát trực tiếp.
  (SoundCloud không cấp link .mp3 trực tiếp — cần widget iframe; để test luồng
  phát nền + repeat/shuffle, dùng mp3 công khai là chuẩn nhất.)
- Video: body.embed_url = link YouTube (VideoModal tự chuyển sang dạng embed).
- Cộng đồng: vài bài có caption để test reactions/comment/lưu.

Idempotent: bỏ qua nếu slug đã tồn tại. Chạy lại an toàn.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.db import SessionLocal
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType

MP3 = [
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3",
]

MUSIC = [
    ("Ngồi Rap Trên Đồi", "DSK", "LIFE RAP", MP3[0]),
    ("Chuyện Tình Rap", "DSK", "LOVE RAP", MP3[1]),
    ("Kèo Này Của Ai", "DSK", "DISSIN'", MP3[2]),
    ("Thử Nghiệm Âm Thanh", "DSK", "Thể Nghiệm", MP3[3]),
    ("Đường Về Nhà", "DSK", "LIFE RAP", MP3[4]),
]

VIDEO = [
    (
        "MV Ngồi Rap Trên Đồi",
        "DSK",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "Video âm nhạc chính thức.",
    ),
    (
        "Hậu Trường Phòng Thu",
        "DSK",
        "https://youtu.be/e-ORhEE9VVg",
        "Behind the scenes buổi thu âm.",
    ),
    (
        "Live Session Acoustic",
        "DSK",
        "https://www.youtube.com/watch?v=3JZ_D3ELwOQ",
        "Bản live mộc tại studio.",
    ),
]

COMMUNITY = [
    (
        "Chào cộng đồng Eskaylation!",
        "Ra mắt không gian cộng đồng — nơi mọi người bàn luận về nhạc, "
        "thả cảm xúc và bình luận realtime.",
    ),
    (
        "Bạn thích thể loại nào nhất?",
        "Life rap, love rap, dissin' hay thể nghiệm? Bình luận bên dưới nhé!",
    ),
    (
        "Ekip đang chuẩn bị dự án mới",
        "Sắp có nhiều bản phát hành trong thời gian tới. Lưu bài để không bỏ lỡ!",
    ),
]


async def _add(session, *, type_, title, slug, summary, body):
    exists = await session.scalar(
        select(Content).where(Content.type == type_, Content.slug == slug)
    )
    if exists:
        print(f"  bỏ qua (đã có): {type_.value}/{slug}")
        return
    session.add(
        Content(
            type=type_,
            status=ContentStatus.published,
            title=title,
            slug=slug,
            summary=summary,
            body=body,
            published_at=datetime.now(UTC),
        )
    )
    print(f"  + {type_.value}/{slug}")


def _slugify(text: str, i: int) -> str:
    import re
    import unicodedata

    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return f"test-{s}-{i}"


async def main() -> None:
    async with SessionLocal() as session:
        print("Nhạc:")
        for i, (title, artist, cat, url) in enumerate(MUSIC):
            await _add(
                session,
                type_=ContentType.music,
                title=title,
                slug=_slugify(title, i),
                summary=None,
                body={"artist": artist, "category": cat, "audio_url": url},
            )
        print("Video:")
        for i, (title, artist, embed, summary) in enumerate(VIDEO):
            await _add(
                session,
                type_=ContentType.video,
                title=title,
                slug=_slugify(title, i),
                summary=summary,
                body={"artist": artist, "embed_url": embed},
            )
        print("Cộng đồng:")
        for i, (title, summary) in enumerate(COMMUNITY):
            await _add(
                session,
                type_=ContentType.community,
                title=title,
                slug=_slugify(title, i),
                summary=summary,
                body={"author": "Eskaylation"},
            )
        await session.commit()
    print("Xong.")


if __name__ == "__main__":
    asyncio.run(main())
