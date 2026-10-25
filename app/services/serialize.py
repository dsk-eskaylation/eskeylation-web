from app.models.content import Content
from app.models.enums import ContentType
from app.schemas.public import AlbumRef, ContentOut, MediaOut
from app.services.media_processing import derived_keys
from app.services.sanitize import player_url, restore_plain_values
from app.services.storage import get_storage


def content_to_out(content: Content) -> ContentOut:
    storage = get_storage()
    media = [
        MediaOut(
            media_id=link.media_id,
            url=storage.url(link.media.storage_key),
            caption=link.caption,
            alt_text=link.media.alt_text,
            is_primary=link.is_primary,
            width=link.media.width,
            height=link.media.height,
            duration=link.media.duration,
            mime_type=link.media.mime_type,
        )
        for link in content.media_links
    ]
    for asset, link in zip(media, content.media_links, strict=True):
        variants = link.media.variants or {}
        allowed = derived_keys(variants, link.media_id)
        if asset.mime_type.startswith("image/"):
            asset.original_url = asset.url
            images = sorted(
                (
                    item
                    for item in variants.get("images", [])
                    if isinstance(item, dict)
                    and item.get("key") in allowed
                    and isinstance(item.get("width"), int)
                    and item["width"] > 0
                ),
                key=lambda item: item["width"],
            )
            if images:
                asset.srcset = ", ".join(
                    f"{storage.url(item['key'])} {item['width']}w" for item in images
                )
                asset.url = storage.url(images[-1]["key"])
        elif asset.mime_type.startswith("video/") and variants.get("poster") in allowed:
            asset.preview_url = storage.url(variants["poster"])
    cover = next(
        (m.url for m in media if m.mime_type.startswith("image/") and m.is_primary),
        next((m.url for m in media if m.mime_type.startswith("image/")), ""),
    )
    body = restore_plain_values(content.body)
    if content.type == ContentType.music:
        audio = next((m for m in media if m.mime_type.startswith("audio/")), None)
        if audio:
            # URL lấy từ media đã gắn, tự đổi theo CDN; không lưu URL hết hạn
            # hay URL cũ trong body khi sửa/gỡ file nhạc trong CMS.
            body["audio_url"] = audio.url
    for asset in media:
        if asset.mime_type.startswith(("audio/", "video/")):
            asset.stream_url = asset.url
            asset.url = cover or asset.preview_url or ""
            asset.preview_url = cover or asset.preview_url or None
        elif asset.mime_type.startswith("image/"):
            asset.original_url = asset.original_url or asset.url
    return ContentOut(
        id=content.public_id or content.id,
        type=content.type,
        title=content.title,
        slug=content.slug,
        summary=content.summary,
        body=body,
        published_at=content.published_at,
        media=media,
        source_url=content.source_url,
        source_provider=content.source_provider,
        player_url=player_url(content.source_url),
        cover_url=content.cover_url,
        album=(
            AlbumRef(
                slug=content.album.slug,
                title=content.album.title,
                kind=content.album.kind,
                year=content.album.year,
            )
            if content.album
            else None
        ),
        track_no=content.track_no,
    )
