"""Shared byte budgets and upload slots; public uploads fail closed without Redis."""

import hashlib
import hmac
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException

from app.config import get_settings
from app.services.ratelimit import _get_redis

logger = logging.getLogger(__name__)
_bytes: dict[str, int] = {}
_slots: dict[str, dict[str, float]] = {}
_day = ""

_CHARGE = """
local amount = tonumber(ARGV[1])
for i, key in ipairs(KEYS) do
    if tonumber(redis.call('GET', key) or '0') + amount > tonumber(ARGV[i+2]) then
        return i
    end
end
for _, key in ipairs(KEYS) do
    redis.call('INCRBY', key, amount)
    redis.call('EXPIRE', key, ARGV[2], 'NX')
end
return 0
"""

_ACQUIRE = """
for _, key in ipairs(KEYS) do
    redis.call('ZREMRANGEBYSCORE', key, '-inf', ARGV[1])
end
for i, key in ipairs(KEYS) do
    if redis.call('ZCARD', key) >= tonumber(ARGV[i+4]) then return i end
end
for _, key in ipairs(KEYS) do
    redis.call('ZADD', key, ARGV[2], ARGV[3])
    redis.call('EXPIRE', key, ARGV[4])
end
return 0
"""

_RELEASE = """
for _, key in ipairs(KEYS) do redis.call('ZREM', key, ARGV[1]) end
return 0
"""


def _scopes(user_id: int, ip: str) -> tuple[str, str, str]:
    # No plaintext client IPs in Redis keys or diagnostic logs.
    digest = hmac.new(
        get_settings().jwt_secret.encode(), ip.encode(), hashlib.sha256
    ).hexdigest()
    return f"user:{user_id}", f"ip:{digest}", "global"


async def _eval(script: str, keys: list[str], args: list) -> int:
    try:
        return int(await _get_redis().eval(script, len(keys), *keys, *args))
    except Exception:
        logger.warning("member_upload_quota_unavailable")
        raise HTTPException(
            503,
            "Tạm thời không kiểm soát được hạn mức tải lên. Vui lòng thử lại.",
            headers={"Retry-After": "30"},
        ) from None


async def charge(user_id: int, ip: str, size: int) -> None:
    """Charge verified bytes atomically before storage. Failed writes keep the charge.

    Conservative accounting avoids refunds after ambiguous storage/DB failures.
    Budgets reset at UTC midnight; deleting a file does not replenish the budget.
    """
    global _day
    if size < 1:
        raise ValueError("Upload size must be positive")
    settings = get_settings()
    now = datetime.now(UTC)
    day = now.date().isoformat()
    retry = max(
        1,
        int(
            (
                datetime.combine(
                    now.date() + timedelta(days=1), datetime.min.time(), UTC
                )
                - now
            ).total_seconds()
        ),
    )
    keys = [f"member-upload:bytes:{day}:{scope}" for scope in _scopes(user_id, ip)]
    limits = [
        settings.member_upload_user_daily_bytes,
        settings.member_upload_ip_daily_bytes,
        settings.member_upload_global_daily_bytes,
    ]
    if settings.is_prod:
        blocked = await _eval(_CHARGE, keys, [size, retry + 3600, *limits])
    else:
        if _day != day:
            _bytes.clear()
            _day = day
        blocked = next(
            (
                i
                for i, (key, limit) in enumerate(zip(keys, limits, strict=True), 1)
                if _bytes.get(key, 0) + size > limit
            ),
            0,
        )
        if not blocked:
            for key in keys:
                _bytes[key] = _bytes.get(key, 0) + size
    if blocked:
        raise HTTPException(
            429,
            "Đã đạt hạn mức dung lượng tải lên trong ngày. "
            "Vui lòng thử lại sau khi hạn mức được làm mới.",
            headers={"Retry-After": str(retry)},
        )


@asynccontextmanager
async def slot(user_id: int, ip: str) -> AsyncIterator[None]:
    """At most 2 uploads/user, 3/IP, 4 total, with bounded leases for crashes."""
    settings = get_settings()
    keys = [f"member-upload:active:{scope}" for scope in _scopes(user_id, ip)]
    token = uuid4().hex
    now = time.time()
    # Leave room for bounded storage retries after the body finished uploading.
    ttl = settings.member_upload_timeout_seconds + 180
    if settings.is_prod:
        blocked = await _eval(_ACQUIRE, keys, [now, now + ttl, token, ttl, 2, 3, 4])
    else:
        for key in list(_slots):
            _slots[key] = {
                t: expiry for t, expiry in _slots[key].items() if expiry > now
            }
            if not _slots[key]:
                del _slots[key]
        blocked = next(
            (
                i
                for i, (key, limit) in enumerate(zip(keys, (2, 3, 4), strict=True), 1)
                if len(_slots.get(key, {})) >= limit
            ),
            0,
        )
        if not blocked:
            for key in keys:
                _slots.setdefault(key, {})[token] = now + ttl
    if blocked:
        raise HTTPException(
            429,
            "Đang có nhiều file được tải lên. Vui lòng đợi rồi thử lại.",
            headers={"Retry-After": "10"},
        )
    try:
        yield
    finally:
        if settings.is_prod:
            # A released response must not become an error; leases expire.
            with suppress(HTTPException):
                await _eval(_RELEASE, keys, [token])
        else:
            for key in keys:
                _slots.get(key, {}).pop(token, None)


def reset() -> None:
    """Clear the dev-only counters between isolated tests."""
    global _day
    _bytes.clear()
    _slots.clear()
    _day = ""
