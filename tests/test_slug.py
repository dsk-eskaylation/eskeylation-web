"""Test tích hợp sinh slug duy nhất (bỏ dấu + hậu tố khi trùng)."""

import pytest

from app.models.enums import ContentStatus, ContentType
from app.services.slug import unique_slug
from tests.conftest import unique_slug as rand_slug

pytestmark = pytest.mark.integration


async def test_slug_bo_dau(db):
    slug = await unique_slug(db, "Đà Lạt Mộng Mơ")
    assert slug == "da-lat-mong-mo"


async def test_slug_title_rong_dung_mac_dinh(db):
    # slugify trả chuỗi rỗng → fallback "noi-dung"
    assert await unique_slug(db, "@@@###") == "noi-dung"


async def test_slug_trung_them_hau_to(db, make_content):
    base = rand_slug("trung")
    # Đã có content với slug = base → lần sinh kế phải thêm -2
    await make_content(slug=base, status=ContentStatus.draft, published=False)
    candidate = await unique_slug(db, base)
    assert candidate == f"{base}-2"


async def test_slug_exclude_id_cho_phep_giu_nguyen(db, make_content):
    base = rand_slug("excl")
    c = await make_content(
        slug=base,
        type_=ContentType.music,
        status=ContentStatus.draft,
        published=False,
    )
    # Loại trừ chính nó → slug giữ nguyên (không thêm hậu tố)
    assert await unique_slug(db, base, exclude_id=c.id) == base
    # Không loại trừ → coi như trùng, thêm hậu tố
    assert await unique_slug(db, base) == f"{base}-2"
