"""Realtime cho cộng đồng qua Redis pub/sub.

Kiến trúc: mỗi tiến trình có một "hub" cục bộ (content_id -> các hàng đợi WS).
Sự kiện được publish lên MỘT kênh Redis chung ("community:events"); một task
nền trong mỗi tiến trình lắng nghe kênh đó rồi fan-out về hàng đợi cục bộ. Nhờ
vậy nhiều instance/worker đều nhận được (scale ngang).

Nếu Redis không sẵn sàng (vd dev chưa bật Redis): publish() fan-out thẳng vào
hub cục bộ -> vẫn realtime trong phạm vi một tiến trình. Không bao giờ chặn API.
"""

import asyncio
import json
import logging

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_CHANNEL = "community:events"

# Trần tổng số kết nối WS đang mở mỗi tiến trình — chống cạn kiệt tài nguyên
# (mỗi kết nối giữ 1 queue + 2 task). WS công khai read-only nên không có auth,
# vì vậy phải chặn ở số lượng để tránh DoS (kể cả bị mở hàng loạt cross-site).
_MAX_CONNECTIONS = 500

# content_id -> tập hàng đợi của các kết nối WS đang mở trong tiến trình này
_hub: dict[int, set[asyncio.Queue[str]]] = {}
_listener_task: asyncio.Task | None = None
_redis_alive = False
_redis = None


def connection_count() -> int:
    """Tổng số kết nối WS đang mở trong tiến trình này."""
    return sum(len(subs) for subs in _hub.values())


def can_register() -> bool:
    """Còn slot để mở thêm kết nối WS không (dưới trần _MAX_CONNECTIONS)."""
    return connection_count() < _MAX_CONNECTIONS


def register(content_id: int) -> asyncio.Queue[str]:
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    _hub.setdefault(content_id, set()).add(q)
    return q


def unregister(content_id: int, q: asyncio.Queue[str]) -> None:
    subs = _hub.get(content_id)
    if subs:
        subs.discard(q)
        if not subs:
            _hub.pop(content_id, None)


def _fanout_local(content_id: int, data: str) -> None:
    for q in _hub.get(content_id, ()):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass  # client chậm -> bỏ sự kiện, không chặn


async def publish(content_id: int, event: dict) -> None:
    """Phát một sự kiện tới mọi người đang xem bài content_id."""
    data = json.dumps({"cid": content_id, "event": event})
    if _redis_alive and _redis is not None:
        try:
            await _redis.publish(_CHANNEL, data)
            return  # listener sẽ fan-out cục bộ khi nhận lại từ Redis
        except Exception:
            logger.warning("Redis publish lỗi — fan-out cục bộ")
    _fanout_local(content_id, json.dumps(event))


async def _listener() -> None:
    global _redis_alive, _redis
    import redis.asyncio as aioredis

    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = _redis.pubsub()
    try:
        await pubsub.subscribe(_CHANNEL)
        _redis_alive = True
        logger.info("Realtime: đã kết nối Redis pub/sub (%s)", _CHANNEL)
        async for msg in pubsub.listen():
            if msg.get("type") != "message":
                continue
            try:
                payload = json.loads(msg["data"])
                _fanout_local(int(payload["cid"]), json.dumps(payload["event"]))
            except (ValueError, KeyError, TypeError):
                continue
    except asyncio.CancelledError:
        raise
    except Exception:
        _redis_alive = False
        logger.warning("Realtime: Redis không sẵn sàng — chạy hub cục bộ (1 tiến trình)")
    finally:
        try:
            await pubsub.aclose()
        except Exception:
            pass


async def start() -> None:
    """Khởi động task lắng nghe Redis (gọi ở startup của app)."""
    global _listener_task
    if _listener_task is None:
        _listener_task = asyncio.create_task(_listener())


async def stop() -> None:
    global _listener_task, _redis, _redis_alive
    if _listener_task is not None:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        _listener_task = None
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:
            pass
        _redis = None
    _redis_alive = False
