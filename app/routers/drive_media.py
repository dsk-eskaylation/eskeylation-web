"""Chỉ phục vụ file đã có trong catalog bằng ID nội bộ, không nhận URL/file ID Drive."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import Response

from app.services import drive_media
from app.services.ratelimit import check_rate


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


@router.get("/{content_id}/stream")
async def read_file(content_id: AssetId, request: Request) -> Response:
    return await drive_media.stream(content_id, request)


@router.head("/{content_id}/stream")
async def file_headers(content_id: AssetId, request: Request) -> Response:
    return await drive_media.stream(content_id, request, head=True)


@router.get("/{content_id}/image")
async def read_image(
    content_id: AssetId, request: Request, w: ImageWidth = 1280
) -> Response:
    return await drive_media.image(content_id, checked_width(w), request)


@router.get("/{content_id}/poster")
async def read_poster(
    content_id: AssetId, request: Request, w: ImageWidth = 960
) -> Response:
    return await drive_media.image(content_id, checked_width(w), request, poster=True)
