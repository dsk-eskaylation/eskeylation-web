"""Read-only deployment gate: broker, processors and a live scheduler heartbeat."""

import argparse
import shutil
import time

from redis import Redis

from app.services.media_jobs import HEARTBEAT_KEY
from scripts.deploy import settings_from_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait", type=int, default=45)
    args = parser.parse_args()
    settings = settings_from_env()
    if not settings.media_processing_enabled:
        print("Media worker disabled by configuration")
        return
    if not all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe")):
        raise SystemExit("Missing ffmpeg/ffprobe")
    deadline = time.monotonic() + min(max(args.wait, 0), 60)
    with Redis.from_url(
        settings.redis_url, socket_connect_timeout=2, socket_timeout=2
    ) as redis:
        while True:
            try:
                redis.ping()
                value = redis.get(HEARTBEAT_KEY)
                if value and 0 <= time.time() - float(value) < 60:
                    print("Media worker heartbeat, Redis and FFmpeg OK")
                    return
            except Exception:
                pass
            if time.monotonic() >= deadline:
                raise SystemExit("No fresh media worker heartbeat")
            time.sleep(2)


if __name__ == "__main__":
    main()
