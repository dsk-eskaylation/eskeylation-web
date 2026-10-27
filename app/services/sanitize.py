"""Chống XSS (bleach) cho rich text và whitelist host cho embed (chống SSRF)."""

import re
from html import unescape
from urllib.parse import parse_qs, quote, urlparse

import bleach
from fastapi import HTTPException, status

from app.config import get_settings
from app.models.enums import MusicProvider

settings = get_settings()

# Key trong body được coi là URL embed video — phải nằm trong host whitelist.
_EMBED_KEYS = ("embed_url", "video_url")
_URL_KEYS = {"audio_url", "embed_url", "video_url"}
_TEXT_KEYS = {
    "artist",
    "author",
    "lyrics",
    "intro",
    "name",
    "role",
    "names",
    "maintain",
}


def _video_target(value: object) -> tuple[MusicProvider, str] | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"}:
            return None
        host = (parsed.hostname or "").removeprefix("www.")
        parts = parsed.path.strip("/").split("/")
        if host == "youtu.be":
            video_id = parts[0]
        elif host == "youtube.com":
            video_id = (
                parts[1]
                if len(parts) == 2 and parts[0] in {"embed", "shorts"}
                else parse_qs(parsed.query).get("v", [""])[0]
                if parsed.path == "/watch"
                else ""
            )
        elif host in {"vimeo.com", "player.vimeo.com"}:
            match = re.fullmatch(r"(?:video/)?(\d+)", parsed.path.strip("/"))
            return (MusicProvider.vimeo, match[1]) if match else None
        else:
            return None
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            return MusicProvider.youtube, video_id
        return None
    except ValueError:
        return None


def playable_video_embed(value: object) -> bool:
    """Match the YouTube/Vimeo URL formats supported by the public player."""
    return _video_target(value) is not None


def music_source(value: object) -> tuple[MusicProvider, str] | None:
    """(provider, embed player URL), or None unless the link is a SoundCloud
    track or a YouTube/Vimeo video."""
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    host = (parsed.hostname or "").removeprefix("www.").removeprefix("m.")
    if host == "soundcloud.com":
        segments = [p for p in parsed.path.split("/") if p]
        if parsed.scheme not in {"http", "https"} or len(segments) < 2:
            return None
        track = quote("https://soundcloud.com/" + "/".join(segments), safe="")
        return MusicProvider.soundcloud, (
            f"https://w.soundcloud.com/player/?url={track}"
            "&auto_play=true&visual=false&show_comments=false"
        )
    target = _video_target(value)
    if target is None:
        return None
    provider, video_id = target
    if provider == MusicProvider.vimeo:
        return provider, f"https://player.vimeo.com/video/{video_id}?autoplay=1"
    return provider, f"https://www.youtube.com/embed/{video_id}?autoplay=1"


def player_url(source_url: str | None) -> str | None:
    found = music_source(source_url)
    return found[1] if found else None


def sanitize_summary(text: str | None) -> str | None:
    """Summary là plain text — bỏ toàn bộ tag HTML."""
    if text is None:
        return None
    return unescape(bleach.clean(text, tags=[], attributes={}, strip=True))


def sanitize_html(value: str) -> str:
    """Giữ lại tag an toàn, loại bỏ script/iframe/on* và tag lạ."""
    return bleach.clean(
        value,
        tags=settings.allowed_html_tags,
        attributes=settings.allowed_html_attributes,
        strip=True,
    )


def sanitize_body(body: dict) -> dict:
    """Làm sạch đệ quy mọi chuỗi trong body (giữ tag an toàn)."""
    return _clean_value(body)


def restore_plain_values(value, key: str = ""):
    """Read legacy entity-encoded fields without rewriting stored content."""
    if isinstance(value, str) and key in _URL_KEYS:
        return value.replace("&amp;", "&")
    if isinstance(value, str) and key in _TEXT_KEYS:
        return (
            unescape(value) if re.search(r"&(?:amp|lt|gt|quot|#\w+);", value) else value
        )
    if isinstance(value, dict):
        return {k: restore_plain_values(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [restore_plain_values(v, key) for v in value]
    return value


def _clean_value(value, key: str = ""):
    if isinstance(value, str):
        if key in _URL_KEYS:
            # URLs are data, never HTML. Publication separately validates sources.
            return value.strip()
        if key in _TEXT_KEYS:
            return sanitize_summary(value)
        return sanitize_html(value)
    if isinstance(value, dict):
        return {k: _clean_value(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean_value(v, key) for v in value]
    return value


def validate_embeds(body: dict) -> None:
    """Chặn embed trỏ tới host ngoài whitelist (chống SSRF / iframe lạ).

    Duyệt ĐỆ QUY toàn bộ body: embed lồng trong list/dict con
    (vd homepage.sections[].video_url) cũng phải qua whitelist.
    """
    _walk_embeds(body)


def _walk_embeds(value) -> None:
    if isinstance(value, dict):
        for key, v in value.items():
            if key in _EMBED_KEYS and v:
                _check_embed_url(key, v)
            else:
                _walk_embeds(v)
    elif isinstance(value, list):
        for v in value:
            _walk_embeds(v)


def _check_embed_url(key: str, url) -> None:
    try:
        parsed = urlparse(str(url))
        host = (parsed.hostname or "").lower()
        allowed = host in settings.allowed_embed_hosts and parsed.scheme in {
            "http",
            "https",
        }
    except ValueError:
        allowed = False
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Embed không hợp lệ ({key}): chỉ cho phép "
                f"{settings.allowed_embed_hosts}"
            ),
        )
