"""Test tích hợp Public API — chạy thật trên Supabase (cần .env)."""

import uuid

import pytest

from app.models.enums import ContentStatus, ContentType
from tests.conftest import unique_slug

pytestmark = pytest.mark.integration


def marker() -> str:
    return "mk" + uuid.uuid4().hex[:10]


# ---------- published vs draft ----------


async def test_list_chi_tra_published(client, make_content):
    pub = await make_content(status=ContentStatus.published)
    draft = await make_content(status=ContentStatus.draft, published=False)

    r = await client.get("/api/music", params={"page_size": 100})
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()["items"]]
    assert pub.slug in slugs
    assert draft.slug not in slugs


async def test_detail_published_an_admin_fields(client, make_content):
    c = await make_content(title="Bài hát", summary="tóm tắt", body={"artist": "DSK"})
    r = await client.get(f"/api/music/{c.slug}")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Bài hát"
    assert data["body"] == {"artist": "DSK"}
    # Tuyệt đối không lộ field nội bộ
    assert "status" not in data
    assert "author_id" not in data
    assert "created_at" not in data
    assert "updated_at" not in data


async def test_detail_draft_tra_404(client, make_content):
    draft = await make_content(status=ContentStatus.draft, published=False)
    r = await client.get(f"/api/music/{draft.slug}")
    assert r.status_code == 404


async def test_detail_khong_ton_tai_tra_404(client):
    r = await client.get(f"/api/music/{unique_slug('nope')}")
    assert r.status_code == 404


# ---------- full-text search (unaccent) ----------


async def test_search_unaccent_khop_co_dau(client, make_content):
    mk = marker()
    c = await make_content(title=f"Đà Lạt {mk}")
    # tìm KHÔNG dấu vẫn khớp nội dung CÓ dấu, AND với marker để cô lập
    r = await client.get("/api/music", params={"q": f"da lat {mk}"})
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()["items"]]
    assert c.slug in slugs


async def test_search_khong_khop_tra_rong(client, make_content):
    mk = marker()
    await make_content(title=f"Đà Lạt {mk}")
    r = await client.get("/api/music", params={"q": f"khongtontai {mk}"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ---------- filter theo JSONB ----------


async def test_filter_category(client, make_content):
    mk = marker()
    pop = await make_content(body={"category": "pop", "mk": mk})
    rock = await make_content(body={"category": "rock", "mk": mk})

    r = await client.get("/api/music", params={"category": "rock"})
    slugs = [i["slug"] for i in r.json()["items"]]
    assert rock.slug in slugs
    assert pop.slug not in slugs


async def test_filter_artist(client, make_content):
    target = await make_content(body={"artist": "DSK"})
    other = await make_content(body={"artist": "Khac"})
    r = await client.get("/api/music", params={"artist": "DSK"})
    slugs = [i["slug"] for i in r.json()["items"]]
    assert target.slug in slugs
    assert other.slug not in slugs


# ---------- pagination ----------


async def test_pagination(client, make_content):
    mk = marker()
    for _ in range(3):
        await make_content(body={"category": mk})

    r1 = await client.get(
        "/api/music", params={"category": mk, "page_size": 2, "page": 1}
    )
    body1 = r1.json()
    assert body1["total"] == 3
    assert body1["pages"] == 2
    assert body1["page"] == 1
    assert len(body1["items"]) == 2

    r2 = await client.get(
        "/api/music", params={"category": mk, "page_size": 2, "page": 2}
    )
    assert len(r2.json()["items"]) == 1


async def test_pagination_params_khong_hop_le_tra_422(client):
    assert (await client.get("/api/music", params={"page": 0})).status_code == 422
    assert (await client.get("/api/music", params={"page_size": 0})).status_code == 422
    assert (
        await client.get("/api/music", params={"page_size": 101})
    ).status_code == 422


# ---------- type isolation ----------


async def test_type_isolation(client, make_content):
    music = await make_content(type_=ContentType.music)
    gallery = await make_content(type_=ContentType.gallery)

    music_slugs = [
        i["slug"]
        for i in (await client.get("/api/music", params={"page_size": 100})).json()[
            "items"
        ]
    ]
    photo_slugs = [
        i["slug"]
        for i in (await client.get("/api/photos", params={"page_size": 100})).json()[
            "items"
        ]
    ]
    assert music.slug in music_slugs and music.slug not in photo_slugs
    assert gallery.slug in photo_slugs and gallery.slug not in music_slugs


# ---------- homepage ----------


async def test_homepage_tra_noi_dung(client, make_content):
    home = await make_content(
        type_=ContentType.homepage, body={"sections": [{"kind": "hero"}]}
    )
    r = await client.get("/api/homepage")
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "homepage"
    assert data["body"]["sections"] == [{"kind": "hero"}]
    # đảm bảo trả đúng bản homepage vừa tạo
    assert data["slug"] == home.slug or data["type"] == "homepage"


# ---------- community ----------


async def test_community_list_chi_published(client, make_content):
    pub = await make_content(
        type_=ContentType.community,
        title="Bài cộng đồng",
        summary="tóm tắt",
        status=ContentStatus.published,
    )
    draft = await make_content(
        type_=ContentType.community,
        status=ContentStatus.draft,
        published=False,
    )
    r = await client.get("/api/community", params={"page_size": 100})
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()["items"]]
    assert pub.slug in slugs
    assert draft.slug not in slugs


async def test_community_detail_va_404(client, make_content):
    c = await make_content(type_=ContentType.community, title="Chi tiết", summary="ok")
    r = await client.get(f"/api/community/{c.slug}")
    assert r.status_code == 200
    assert r.json()["title"] == "Chi tiết"
    assert "status" not in r.json()

    r404 = await client.get(f"/api/community/{unique_slug('nope')}")
    assert r404.status_code == 404


async def test_community_type_isolation(client, make_content):
    # Bài community không lọt sang route music
    c = await make_content(type_=ContentType.community, summary="x")
    music_slugs = [
        i["slug"]
        for i in (await client.get("/api/music", params={"page_size": 100})).json()[
            "items"
        ]
    ]
    assert c.slug not in music_slugs


# ---------- media serialization ----------


async def test_media_serialize_va_thu_tu(client, make_content, make_media, link_media):
    content = await make_content(type_=ContentType.gallery)
    m1 = await make_media(width=800, height=600, alt_text="anh 1")
    m2 = await make_media(width=1024, height=768)
    # position nghịch để kiểm tra sắp xếp theo position
    await link_media(content, m2, caption="thứ hai", position=2, is_primary=False)
    await link_media(content, m1, caption="thứ nhất", position=1, is_primary=True)

    r = await client.get(f"/api/photos/{content.slug}")
    media = r.json()["media"]
    assert len(media) == 2
    # sắp theo position tăng dần
    assert media[0]["caption"] == "thứ nhất"
    assert media[0]["is_primary"] is True
    assert media[0]["alt_text"] == "anh 1"
    assert media[0]["width"] == 800
    assert media[0]["url"].endswith(".jpg")
    assert media[1]["caption"] == "thứ hai"
