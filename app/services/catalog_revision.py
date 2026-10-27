"""A database revision that changes on publish, edit, media changes and deletion."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def database_revision(session: AsyncSession) -> str:
    # One statement/snapshot and a small scalar result. Both FK joins are indexed.
    return await session.scalar(
        text(
            """
            SELECT md5(
              coalesce((SELECT string_agg(id::text || ':' || updated_at::text,
                                         ',' ORDER BY id)
                        FROM public.contents WHERE status='published'), '') || '|' ||
              coalesce((SELECT string_agg(
                          concat_ws(':', m.id, m.content_id, m.media_id, m.position,
                                    m.is_primary, m.caption, a.updated_at),
                          ',' ORDER BY m.id)
                        FROM public.content_media m
                        JOIN public.contents c ON c.id=m.content_id
                        JOIN public.media a ON a.id=m.media_id
                        WHERE c.status='published'), '') || '|' ||
              coalesce((SELECT string_agg(id::text || ':' || updated_at::text,
                                         ',' ORDER BY id)
                        FROM public.albums), '')
            )
            """
        )
    )
