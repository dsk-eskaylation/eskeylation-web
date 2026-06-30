"""Chống XSS (bleach) cho rich text và whitelist host cho embed (chống SSRF)."""

from urllib.parse import urlparse

import bleach
from fastapi import HTTPException, status

from app.config import get_settings

settings = get_settings()

# Key trong body được coi là URL embed video — phải nằm trong host whitelist.
_EMBED_KEYS = ("embed_url", "video_url")


def sanitize_summary(text: str | None) -> str | None:
    """Summary là plain text — bỏ toàn bộ tag HTML."""
    if text is None:
        return None
    return bleach.clean(text, tags=[], attributes={}, strip=True)


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


def _clean_value(value):
    if isinstance(value, str):
        return sanitize_html(value)
    if isinstance(value, dict):
        return {k: _clean_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean_value(v) for v in value]
    return value


def validate_embeds(body: dict) -> None:
    """Chặn embed trỏ tới host ngoài whitelist (chống SSRF / iframe lạ)."""
    for key in _EMBED_KEYS:
        url = body.get(key)
        if not url:
            continue
        parsed = urlparse(str(url))
        host = (parsed.hostname or "").lower()
        allowed = host in settings.allowed_embed_hosts
        if parsed.scheme not in ("http", "https") or not allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Embed không hợp lệ ({key}): chỉ cho phép "
                    f"{settings.allowed_embed_hosts}"
                ),
            )
