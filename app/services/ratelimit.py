"""Rate limit in-memory (cửa sổ trượt) cho endpoint nhạy cảm (login/register).

Đủ cho 1 instance uvicorn. Khi scale nhiều instance thì chuyển sang Redis
(đã có trong stack cho Celery) — giữ nguyên interface check_rate().
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

_hits: defaultdict[str, deque[float]] = defaultdict(deque)


def check_rate(key: str, limit: int, window_seconds: float = 60.0) -> None:
    """Ném 429 nếu key vượt quá `limit` lần trong `window_seconds`."""
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window_seconds:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều yêu cầu. Vui lòng thử lại sau ít phút.",
        )
    q.append(now)


def reset() -> None:
    """Xoá toàn bộ bộ đếm — chỉ dùng trong test."""
    _hits.clear()
