"""Chỉ phục vụ file đã có trong catalog bằng ID nội bộ, không nhận URL/file ID Drive."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.db import SessionLocal
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType
from app.models.interaction_target import InteractionTarget
from app.models.media import ContentMedia
from app.services import drive_media
from app.services.ratelimit import check_rate
from app.services.serialize import content_to_out


async def same_site_media(request: Request) -> None:
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Không cho phép nhúng tư liệu từ website khác")
    ip = request.client.host if request.client else "unknown"
    await check_rate(f"media:{ip}", limit=300, window_seconds=60)


router = APIRouter(
    prefix="/api/library", tags=["library"], dependencies=[Depends(same_site_media)]
)
AssetId = Annotated[int, Path(ge=-(2**48), le=-1)]
ImageWidth = Annotated[int, Query(ge=320, le=1920)]


def checked_width(width: int) -> int:
    if width not in (320, 640, 960, 1280, 1920):
        raise HTTPException(422, "Kích thước ảnh không được hỗ trợ")
    return width


async def migrated_media(content_id: int, *, image: bool = False) -> Response | None:
    if get_settings().public_content_source == "drive":
        return None
    async with SessionLocal() as session:
        content = (
            (
                await session.scalars(
                    select(Content)
                    .join(InteractionTarget, InteractionTarget.content_id == Content.id)
                    .where(
                        InteractionTarget.id == content_id,
                        Content.status == ContentStatus.published,
                    )
                    .options(
                        joinedload(Content.media_links).joinedload(ContentMedia.media)
                    )
                )
            )
            .unique()
            .one_or_none()
        )
        if content is None:
            raise HTTPException(404, "Không tìm thấy tư liệu")
        assets = content_to_out(content).media
        if image:
            assets = [m for m in assets if m.mime_type.startswith("image/")]
        elif content.type in {ContentType.music, ContentType.video}:
            prefix = "audio/" if content.type == ContentType.music else "video/"
            assets = [m for m in assets if m.mime_type.startswith(prefix)]
        asset = next((m for m in assets if m.is_primary), assets[0] if assets else None)
        if asset is None:
            raise HTTPException(404, "Không tìm thấy tư liệu")
        url = (
            asset.url if image else asset.stream_url or asset.original_url or asset.url
        )
        return RedirectResponse(
            url, status_code=307, headers={"Cache-Control": "public, max-age=30"}
        )


@router.get("/{content_id}/stream")
async def read_file(content_id: AssetId, request: Request) -> Response:
    migrated = await migrated_media(content_id)
    if migrated is not None:
        return migrated
    return await drive_media.stream(content_id, request)


@router.head("/{content_id}/stream")
async def file_headers(content_id: AssetId, request: Request) -> Response:
    migrated = await migrated_media(content_id)
    if migrated is not None:
        return migrated
    return await drive_media.stream(content_id, request, head=True)


@router.get("/{content_id}/image")
async def read_image(
    content_id: AssetId, request: Request, w: ImageWidth = 1280
) -> Response:
    checked_width(w)
    migrated = await migrated_media(content_id, image=True)
    if migrated is not None:
        return migrated
    return await drive_media.image(content_id, checked_width(w), request)


@router.get("/{content_id}/poster")
async def read_poster(
    content_id: AssetId, request: Request, w: ImageWidth = 960
) -> Response:
    checked_width(w)
    migrated = await migrated_media(content_id, image=True)
    if migrated is not None:
        return migrated
    return await drive_media.image(content_id, checked_width(w), request, poster=True)
