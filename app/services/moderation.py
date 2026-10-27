"""Kiểm duyệt từ ngữ: chặn nội dung/bình luận chứa từ trong danh sách cấm.

Danh sách từ cấm do admin quản lý (bảng banned_words). Vì thao tác kiểm tra chạy
mỗi lần tạo/sửa nội dung và gửi bình luận, danh sách được CACHE trong tiến trình
(TTL ngắn) để không phải round-trip DB mỗi lần; cache tự làm mới sau TTL và bị
xoá ngay khi admin thêm/xoá từ (invalidate()).

Khớp KHÔNG phân biệt hoa/thường, sau khi chuẩn hoá NFC (bàn phím/macOS có thể gửi
chữ Việt dạng tổ hợp NFD, làm 'người' tách thành 'ngu'+'o'+'i'). Từ và cụm từ đều
phải đứng nguyên vẹn giữa ranh giới từ -> 'ngu' không dính 'người', 'óc chó' không
dính 'móc chó'. Admin tự thêm biến thể (có dấu / không dấu / viết tắt) tuỳ nhu cầu.
"""

import re
import time
import unicodedata
from collections.abc import Iterator

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.moderation import BannedWord

BLOCKED_MESSAGE = "Không thể đăng được do chứa từ khóa nhạy cảm"
_TTL = 30.0  # giây — độ trễ tối đa để từ cấm mới có hiệu lực toàn tiến trình

_cache: list[tuple[str, re.Pattern[str]]] | None = None
_cache_at: float = 0.0


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


async def _load(session: AsyncSession) -> list[tuple[str, re.Pattern[str]]]:
    rows = await session.scalars(select(BannedWord.word))
    return _compile(rows.all())


def _compile(words: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    unique = sorted({normalize(w) for w in words})
    return [(w, re.compile(rf"(?<!\w){re.escape(w)}(?!\w)")) for w in unique]


async def get_words(session: AsyncSession) -> list[tuple[str, re.Pattern[str]]]:
    global _cache, _cache_at
    now = time.monotonic()
    if _cache is None or now - _cache_at > _TTL:
        _cache = await _load(session)
        _cache_at = now
    return _cache


def invalidate() -> None:
    """Xoá cache -> lần kiểm tra sau nạp lại từ DB (gọi khi admin thêm/xoá từ)."""
    global _cache
    _cache = None


def _find_hits(text: str, words: list[tuple[str, re.Pattern[str]]]) -> set[str]:
    if not text:
        return set()
    low = normalize(text)
    return {w for w, pattern in words if pattern.search(low)}


def _iter_strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _iter_strings(v)


async def assert_clean(
    session: AsyncSession,
    *,
    summary: str | None = None,
    body: dict | None = None,
    text: str | None = None,
) -> None:
    """Ném 422 nếu bất kỳ đoạn văn bản nào chứa từ cấm.

    - summary/text: chuỗi phẳng.
    - body: dict -> duyệt đệ quy mọi chuỗi bên trong.
    """
    words = await get_words(session)
    if not words:
        return
    hits: set[str] = set()
    for t in (summary, text):
        if t:
            hits |= _find_hits(t, words)
    if body:
        for s in _iter_strings(body):
            hits |= _find_hits(s, words)
    if hits:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=BLOCKED_MESSAGE,
        )
