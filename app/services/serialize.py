from app.models.content import Content
from app.schemas.public import ContentOut, MediaOut
from app.services.storage import get_storage


def content_to_out(content: Content) -> ContentOut:
    storage = get_storage()
    media = [
        MediaOut(
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
    return ContentOut(
        id=content.id,
        type=content.type,
        title=content.title,
        slug=content.slug,
        summary=content.summary,
        body=content.body,
        published_at=content.published_at,
        media=media,
    )
