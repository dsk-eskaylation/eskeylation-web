"""Rate limit cho endpoint nhạy cảm (login/register).

- prod: Redis (fixed window INCR+EXPIRE) — bộ đếm dùng CHUNG giữa mọi
  worker/instance, scale ngang không làm loãng giới hạn.
- dev/test hoặc Redis lỗi: fallback in-memory (cửa sổ trượt, per-process).
Interface check_rate() giữ nguyên cho mọi caller.
"""

import logging
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_hits: defaultdict[str, deque[float]] = defaultdict(deque)
_redis = None


def _too_many() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Quá nhiều yêu cầu. Vui lòng thử lại sau ít phút.",
    )


def _get_redis():
    global _redis
    if _redis is None:
        import redis.asyncio as aioredis

        _redis = aioredis.from_url(
            settings.redis_url,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
    return _redis


async def _check_redis(key: str, limit: int, window_seconds: float) -> None:
    redis_key = f"rl:{key}"
    r = _get_redis()
    pipe = r.pipeline()
    pipe.incr(redis_key)
    pipe.expire(redis_key, int(window_seconds), nx=True)
    count, _ = await pipe.execute()
    if int(count) > limit:
        raise _too_many()


def _check_memory(key: str, limit: int, window_seconds: float) -> None:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window_seconds:
        q.popleft()
    if len(q) >= limit:
        raise _too_many()
    q.append(now)


async def check_rate(key: str, limit: int, window_seconds: float = 60.0) -> None:
    """Ném 429 nếu key vượt quá `limit` lần trong `window_seconds`."""
    if settings.is_prod:
        try:
            await _check_redis(key, limit, window_seconds)
            return
        except HTTPException:
            raise
        except Exception:
            logger.warning("Redis rate-limit lỗi — fallback in-memory")
    _check_memory(key, limit, window_seconds)


def reset() -> None:
    """Xoá toàn bộ bộ đếm in-memory — chỉ dùng trong test."""
    _hits.clear()
