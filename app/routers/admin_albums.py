from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_role
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.album import AlbumAdminRead, AlbumIn, AlbumUpdate
from app.services import activity, albums

router = APIRouter(prefix="/admin/albums", tags=["cms"])

_editor = require_role(UserRole.admin, UserRole.editor, UserRole.author)
_publisher = require_role(UserRole.admin, UserRole.editor)


@router.get("", response_model=list[AlbumAdminRead])
async def list_albums(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(_editor),
) -> list[AlbumAdminRead]:
    return await albums.list_admin(session)


@router.post("", response_model=AlbumAdminRead, status_code=status.HTTP_201_CREATED)
async def create_album(
    data: AlbumIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_publisher),
) -> AlbumAdminRead:
    album = await albums.create(session, data)
    await activity.log(
        session,
        actor=user,
        action=activity.CREATE,
        entity_type="album",
        entity_id=album.id,
        entity_title=album.title,
    )
    return album


@router.patch("/{album_id}", response_model=AlbumAdminRead)
async def update_album(
    album_id: int,
    data: AlbumUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_publisher),
) -> AlbumAdminRead:
    album = await albums.update(session, await albums.get(session, album_id), data)
    await activity.log(
        session,
        actor=user,
        action=activity.UPDATE,
        entity_type="album",
        entity_id=album.id,
        entity_title=album.title,
    )
    return album


@router.delete("/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_album(
    album_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(_publisher),
) -> None:
    album = await albums.get(session, album_id)
    title = album.title
    await albums.delete(session, album)
    await activity.log(
        session,
        actor=user,
        action=activity.DELETE,
        entity_type="album",
        entity_id=album_id,
        entity_title=title,
    )
