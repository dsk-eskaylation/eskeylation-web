"""Test tích hợp sinh slug duy nhất (bỏ dấu + hậu tố khi trùng, unique theo type)."""

import pytest

from app.models.enums import ContentStatus, ContentType
from app.services.slug import unique_slug
from tests.conftest import unique_slug as rand_slug

pytestmark = pytest.mark.integration


async def test_slug_bo_dau(db):
    slug = await unique_slug(db, "Đà Lạt Mộng Mơ", ContentType.music)
    assert slug == "da-lat-mong-mo"


async def test_slug_title_rong_dung_mac_dinh(db):
    # slugify trả chuỗi rỗng → fallback "noi-dung"
    assert await unique_slug(db, "@@@###", ContentType.music) == "noi-dung"


async def test_slug_trung_them_hau_to(db, make_content):
    base = rand_slug("trung")
    # Đã có content CÙNG TYPE với slug = base → lần sinh kế phải thêm -2
    await make_content(
        slug=base,
        type_=ContentType.music,
        status=ContentStatus.draft,
        published=False,
    )
    candidate = await unique_slug(db, base, ContentType.music)
    assert candidate == f"{base}-2"


async def test_slug_khac_type_duoc_dung_lai(db, make_content):
    # Slug unique THEO TYPE: gallery được dùng slug đã tồn tại bên music
    base = rand_slug("pertype")
    await make_content(
        slug=base,
        type_=ContentType.music,
        status=ContentStatus.draft,
        published=False,
    )
    assert await unique_slug(db, base, ContentType.gallery) == base


async def test_slug_exclude_id_cho_phep_giu_nguyen(db, make_content):
    base = rand_slug("excl")
    c = await make_content(
        slug=base,
        type_=ContentType.music,
        status=ContentStatus.draft,
        published=False,
    )
    # Loại trừ chính nó → slug giữ nguyên (không thêm hậu tố)
    assert await unique_slug(db, base, ContentType.music, exclude_id=c.id) == base
    # Không loại trừ → coi như trùng, thêm hậu tố
    assert await unique_slug(db, base, ContentType.music) == f"{base}-2"
