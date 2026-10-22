"""Real Redis + separate Celery process + FFmpeg, with synthetic local files."""

import asyncio
import os
import shutil
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit

import pytest
from PIL import Image

from app.config import get_settings
from app.services import media_jobs

pytestmark = pytest.mark.skipif(
    os.environ.get("MEDIA_WORKER_INTEGRATION") != "1",
    reason="Real worker gate runs in CI with isolated Redis and FFmpeg",
)


async def test_separate_worker_process_handles_image_audio_video_and_heartbeat(
    db, make_media, tmp_path, monkeypatch
):
    from redis import Redis

    settings = get_settings()
    parsed = urlsplit(settings.redis_url)
    assert parsed.hostname in {"localhost", "127.0.0.1"} and parsed.path == "/15"
    assert shutil.which("ffmpeg") and shutil.which("ffprobe")
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    image = await make_media(storage_key="image.png", mime_type="image/png")
    video = await make_media(storage_key="video.mp4", mime_type="video/mp4")
    audio = await make_media(storage_key="audio.mp3", mime_type="audio/mpeg")
    Image.new("RGB", (1200, 600), "blue").save(tmp_path / image.storage_key)
    for arguments, filename in [
        (
            [
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=320x180:r=10",
                "-t",
                "0.6",
                "-c:v",
                "mpeg4",
            ],
            video.storage_key,
        ),
        (
            [
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=0.6",
                "-c:a",
                "libmp3lame",
            ],
            audio.storage_key,
        ),
    ]:
        await asyncio.to_thread(
            subprocess.run,
            ["ffmpeg", "-v", "error", "-nostdin", *arguments, str(tmp_path / filename)],
            check=True,
            timeout=15,
        )
    for media in (image, video, audio):
        media_jobs.queue(media)
    await db.commit()
    env = os.environ.copy()
    env.update(
        MEDIA_PROCESSING_ENABLED="true", MEDIA_ROOT=str(tmp_path), PYTHONUTF8="1"
    )
    with Redis.from_url(settings.redis_url, socket_timeout=2) as redis:
        redis.ping()
        redis.delete(media_jobs.HEARTBEAT_KEY)
    with (tmp_path / "worker.log").open("w", encoding="utf-8") as log:
        worker = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "app.workers.celery_app:celery_app",
                "worker",
                "--beat",
                "--schedule",
                str(tmp_path / "beat"),
                "--pool",
                "solo",
                "--concurrency",
                "1",
                "--loglevel",
                "INFO",
                "--without-gossip",
                "--without-mingle",
            ],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 80
            while time.monotonic() < deadline:
                assert worker.poll() is None, (tmp_path / "worker.log").read_text()[
                    -4000:
                ]
                for media in (image, video, audio):
                    await db.refresh(media)
                if all(
                    media.processing_status == "ready"
                    for media in (image, video, audio)
                ):
                    break
                await db.commit()
                await asyncio.sleep(1)
            assert [media.processing_status for media in (image, video, audio)] == [
                "ready"
            ] * 3, (tmp_path / "worker.log").read_text()[-4000:]
            assert image.variants["images"][0]["width"] == 480
            assert (video.width, video.height) == (320, 180)
            assert video.duration > 0 and audio.duration > 0
            with Image.open(tmp_path / video.variants["poster"]) as poster:
                assert poster.size == (320, 180)
            with Redis.from_url(settings.redis_url, socket_timeout=2) as redis:
                assert redis.exists(media_jobs.HEARTBEAT_KEY)
        finally:
            worker.terminate()
            try:
                await asyncio.to_thread(worker.wait, timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(worker.pid, signal.SIGKILL)
                worker.wait(timeout=5)
