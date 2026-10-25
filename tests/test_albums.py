import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.models.album import Album
from app.models.enums import UserRole
from tests.test_cms_api import _create, auth, token_for


@pytest_asyncio.fixture
async def track_albums(db):
    ids: list[int] = []
    yield ids
    if ids:
        await db.execute(delete(Album).where(Album.id.in_(ids)))
        await db.commit()


async def _album(client, token, track, **payload) -> dict:
    r = await client.post("/admin/albums", json=payload, headers=auth(token))
    assert r.status_code == 201, r.text
    track.append(r.json()["id"])
    return r.json()


async def _track(client, token, track, title, album_id=None, track_no=None, **body):
    content = await _create(
        client,
        token,
        track,
        type="music",
        title=title,
        body={"artist": "DSK", **body},
        source_url="https://youtu.be/abcdefghijk",
        album_id=album_id,
        track_no=track_no,
    )
    r = await client.post(
        f"/admin/content/{content['id']}/publish", headers=auth(token)
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_album_lists_tracks_in_order_and_filters_music(
    client, make_user, track_content, track_albums
):
    token = await token_for(client, make_user, UserRole.admin)
    album = await _album(
        client, token, track_albums, title="Waking Life Test", kind="mixtape", year=2009
    )
    await _track(client, token, track_content, "Mama", album["id"], 2)
    await _track(client, token, track_content, "Intro", album["id"], 1)
    await _track(client, token, track_content, "Bài lẻ")

    listed = (await client.get("/api/albums")).json()
    mine = next(a for a in listed if a["slug"] == album["slug"])
    assert mine["track_count"] == 2 and mine["kind"] == "mixtape"

    detail = (await client.get(f"/api/albums/{album['slug']}")).json()
    assert [t["title"] for t in detail["tracks"]] == ["Intro", "Mama"]
    assert detail["tracks"][0]["album"]["slug"] == album["slug"]

    page = (await client.get("/api/music", params={"album": album["slug"]})).json()
    assert [t["track_no"] for t in page["items"]] == [1, 2]


async def test_empty_album_is_hidden_publicly(client, make_user, track_albums):
    token = await token_for(client, make_user, UserRole.admin)
    album = await _album(client, token, track_albums, title="Chưa có bài")
    public = {a["slug"] for a in (await client.get("/api/albums")).json()}
    assert album["slug"] not in public
    assert (await client.get(f"/api/albums/{album['slug']}")).status_code == 404


async def test_track_numbers_are_unique_per_album(
    client, make_user, track_content, track_albums
):
    token = await token_for(client, make_user, UserRole.admin)
    album = await _album(client, token, track_albums, title="Số trùng")
    await _track(client, token, track_content, "Một", album["id"], 1)
    r = await client.post(
        "/admin/content",
        json={
            "type": "music",
            "title": "Hai",
            "body": {"artist": "DSK"},
            "album_id": album["id"],
            "track_no": 1,
        },
        headers=auth(token),
    )
    assert r.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "video", "title": "x", "album_id": -1},
        {"type": "music", "title": "x", "album_id": 999_999_999},
        {"type": "music", "title": "x", "body": {"category": "POP"}},
    ],
)
async def test_invalid_album_or_genre_rejected(client, make_user, payload):
    token = await token_for(client, make_user, UserRole.admin)
    r = await client.post("/admin/content", json=payload, headers=auth(token))
    assert r.status_code == 422


async def test_deleting_album_keeps_tracks(
    client, make_user, track_content, track_albums
):
    token = await token_for(client, make_user, UserRole.admin)
    album = await _album(client, token, track_albums, title="Sẽ xoá")
    track = await _track(client, token, track_content, "Còn lại", album["id"], 1)
    r = await client.delete(f"/admin/albums/{album['id']}", headers=auth(token))
    assert r.status_code == 204
    track_albums.remove(album["id"])
    after = await client.get(f"/admin/content/{track['id']}", headers=auth(token))
    assert after.json()["album_id"] is None


async def test_album_admin_requires_publisher(client, make_user):
    token = await token_for(client, make_user, UserRole.author)
    r = await client.post("/admin/albums", json={"title": "x"}, headers=auth(token))
    assert r.status_code == 403


async def test_genre_counts_cover_configured_genres(client, make_user, track_content):
    token = await token_for(client, make_user, UserRole.admin)
    await _track(client, token, track_content, "Đời", category="LIFE RAP")
    genres = (await client.get("/api/music/genres")).json()
    counts = {g["name"]: g["count"] for g in genres}
    assert counts["LIFE RAP"] >= 1 and "LOVE RAP" in counts


async def test_singles_filter_returns_only_tracks_without_album(
    client, make_user, track_content, track_albums
):
    token = await token_for(client, make_user, UserRole.admin)
    album = await _album(client, token, track_albums, title="Có album")
    await _track(client, token, track_content, "Trong album", album["id"], 1)
    single = await _track(client, token, track_content, "Bài lẻ test")
    page = (
        await client.get("/api/music", params={"singles": "true", "page_size": 100})
    ).json()
    titles = {t["title"] for t in page["items"]}
    assert single["title"] in titles and "Trong album" not in titles
    assert all(t["album"] is None for t in page["items"])
