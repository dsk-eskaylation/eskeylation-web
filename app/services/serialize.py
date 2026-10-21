from app.models.content import Content
from app.models.enums import ContentType
from app.schemas.public import ContentOut, MediaOut
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
    cover = next(
        (m.url for m in media if m.mime_type.startswith("image/") and m.is_primary),
        next((m.url for m in media if m.mime_type.startswith("image/")), ""),
    )
    body = dict(content.body)
    if content.type == ContentType.music:
        audio = next((m for m in media if m.mime_type.startswith("audio/")), None)
        if audio:
            # URL lấy từ media đã gắn, tự đổi theo CDN; không lưu URL hết hạn
            # hay URL cũ trong body khi sửa/gỡ file nhạc trong CMS.
            body["audio_url"] = audio.url
    for asset in media:
        if asset.mime_type.startswith(("audio/", "video/")):
            asset.stream_url = asset.url
            asset.url = cover
            asset.preview_url = cover or None
        elif asset.mime_type.startswith("image/"):
            asset.original_url = asset.url
    return ContentOut(
        id=content.public_id or content.id,
        type=content.type,
        title=content.title,
        slug=content.slug,
        summary=content.summary,
        body=body,
        published_at=content.published_at,
        media=media,
    )
