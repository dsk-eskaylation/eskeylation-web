"""Bounded media transforms. Only the background worker calls this module."""

import io
import json
import logging
import math
import subprocess
import tempfile
import warnings
from pathlib import Path

from PIL import Image, ImageOps

from app.config import get_settings
from app.services.storage import Storage


class ProcessingError(Exception):
    """A fixed error code suitable for CMS and logs."""


def derived_keys(variants: dict, media_id: int) -> set[str]:
    prefix = f"derived/{media_id}/"
    values = [
        item.get("key") for item in variants.get("images", []) if isinstance(item, dict)
    ]
    values.append(variants.get("poster"))
    return {
        key
        for key in values
        if isinstance(key, str)
        and key.startswith(prefix)
        and ".." not in key
        and "\\" not in key
    }


def cleanup(storage: Storage, keys: set[str]) -> None:
    for key in keys:
        try:
            storage.delete(key)
        except Exception:
            logging.getLogger(__name__).warning("media_derivative_cleanup_failed")


def _command(args: list[str], timeout: int) -> str:
    try:
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=True,
        )
        return result.stdout.decode("utf-8")
    except FileNotFoundError:
        raise ProcessingError("processor_unavailable") from None
    except subprocess.TimeoutExpired:
        raise ProcessingError("processing_timeout") from None
    except (subprocess.CalledProcessError, UnicodeError):
        raise ProcessingError("invalid_media") from None


def process_file(
    storage: Storage, media_id: int, token: str, key: str, mime: str
) -> dict:
    settings = get_settings()
    max_bytes = (
        settings.max_image_size
        if mime.startswith("image/")
        else settings.max_video_size
        if mime.startswith("video/")
        else settings.max_audio_size
    )
    saved: set[str] = set()
    variants: dict = {}
    result: dict = {"variants": variants}
    prefix = f"derived/{media_id}/{token}"
    try:
        with tempfile.TemporaryDirectory(prefix="eskaylation-media-") as directory:
            source = Path(directory) / "source"
            storage.download(key, source, max_bytes)
            if mime.startswith("image/"):
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(source) as original:
                        if original.width * original.height > 16_000_000:
                            raise ProcessingError("image_too_large")
                        if getattr(original, "is_animated", False):
                            return result
                        image = ImageOps.exif_transpose(original)
                        result.update(width=image.width, height=image.height)
                        image = image.convert(
                            "RGBA"
                            if "A" in image.getbands() or "transparency" in image.info
                            else "RGB"
                        )
                        images = []
                        for width in sorted(
                            {min(image.width, size) for size in (480, 960, 1600, 2560)}
                        ):
                            resized = image.copy()
                            resized.thumbnail(
                                (
                                    width,
                                    max(1, round(image.height * width / image.width)),
                                ),
                                Image.Resampling.LANCZOS,
                            )
                            buffer = io.BytesIO()
                            resized.save(buffer, format="WEBP", quality=88, method=4)
                            variant_key = f"{prefix}/image-{resized.width}.webp"
                            saved.add(variant_key)
                            storage.save(variant_key, buffer.getvalue())
                            images.append(
                                {
                                    "key": variant_key,
                                    "width": resized.width,
                                    "height": resized.height,
                                }
                            )
                        variants["images"] = images
            elif mime.startswith(("video/", "audio/")):
                demuxer = {
                    "video/mp4": "mov",
                    "video/webm": "matroska",
                    "audio/mpeg": "mp3",
                }.get(mime)
                if demuxer is None:
                    raise ProcessingError("unsupported_media")
                input_options = [
                    "-protocol_whitelist",
                    "file",
                    "-max_alloc",
                    "67108864",
                    "-probesize",
                    "5000000",
                    "-analyzeduration",
                    "5000000",
                    "-max_streams",
                    "16",
                    "-f",
                    demuxer,
                ]
                probe = json.loads(
                    _command(
                        [
                            "ffprobe",
                            "-v",
                            "error",
                            *input_options,
                            "-show_entries",
                            "format=duration:stream=codec_type,width,height,duration",
                            "-of",
                            "json",
                            str(source),
                        ],
                        30,
                    )
                )
                streams = probe.get("streams", [])
                duration = float(probe.get("format", {}).get("duration", 0))
                if math.isfinite(duration) and duration > 0:
                    result["duration"] = duration
                if mime.startswith("video/"):
                    video = next(
                        (s for s in streams if s.get("codec_type") == "video"), None
                    )
                    if not video or not video.get("width") or not video.get("height"):
                        raise ProcessingError("invalid_media")
                    result.update(
                        width=int(video["width"]), height=int(video["height"])
                    )
                    if (
                        result["width"] <= 0
                        or result["height"] <= 0
                        or result["width"] * result["height"] > 16_000_000
                    ):
                        raise ProcessingError("video_too_large")
                    poster = Path(directory) / "poster.jpg"
                    _command(
                        [
                            "ffmpeg",
                            "-v",
                            "error",
                            "-nostdin",
                            *input_options,
                            "-threads",
                            "1",
                            "-i",
                            str(source),
                            "-map",
                            "0:v:0",
                            "-an",
                            "-sn",
                            "-dn",
                            "-map_metadata",
                            "-1",
                            "-frames:v",
                            "1",
                            "-vf",
                            "scale=w='min(1280,iw)':h=-2",
                            "-threads",
                            "1",
                            "-q:v",
                            "2",
                            str(poster),
                        ],
                        60,
                    )
                    poster_key = f"{prefix}/poster.jpg"
                    saved.add(poster_key)
                    storage.save(poster_key, poster.read_bytes())
                    variants["poster"] = poster_key
            else:
                raise ProcessingError("unsupported_media")
        return result
    except Exception:
        cleanup(storage, saved)
        raise
