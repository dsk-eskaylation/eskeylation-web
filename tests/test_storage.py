"""Test storage abstraction: selection, LocalStorage roundtrip, Supabase (guarded)."""

import os
import uuid

import pytest

from app.config import get_settings
from app.services.storage import LocalStorage, SupabaseStorage, get_storage

_settings = get_settings()
_supabase_configured = bool(
    os.environ.get("ALLOW_CLOUD_STORAGE_TESTS") == "1"
    and os.environ.get("SUPABASE_TEST_URL")
    and os.environ.get("SUPABASE_TEST_SERVICE_KEY")
    and os.environ.get("SUPABASE_TEST_BUCKET", "").startswith("test-")
)


# ---------- selection (unit) ----------


def test_get_storage_chon_local(monkeypatch):
    monkeypatch.setattr(_settings, "storage_backend", "local")
    assert isinstance(get_storage(), LocalStorage)


def test_get_storage_chon_supabase(monkeypatch):
    monkeypatch.setattr(_settings, "storage_backend", "supabase")
    monkeypatch.setattr(_settings, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(_settings, "supabase_service_key", "k")
    assert isinstance(get_storage(), SupabaseStorage)


def test_supabase_url_la_public_cdn():
    s = SupabaseStorage("https://x.supabase.co/", "k", "media")
    assert (
        s.url("a/b.jpg")
        == "https://x.supabase.co/storage/v1/object/public/media/a/b.jpg"
    )


# ---------- LocalStorage roundtrip (unit) ----------


def test_local_storage_roundtrip(tmp_path):
    s = LocalStorage(str(tmp_path))
    s.save("d/f.txt", b"hi")
    assert s.read("d/f.txt") == b"hi"
    assert s.url("d/f.txt").endswith("/d/f.txt")
    s.delete("d/f.txt")
    s.delete("d/f.txt")  # xoá file không tồn tại không được lỗi


def test_local_storage_url_does_not_expose_filesystem_root(tmp_path):
    s = LocalStorage(str(tmp_path))
    assert s.url("music/a b.mp3") == "/media/music/a%20b.mp3"


# ---------- Supabase roundtrip thật (chỉ chạy khi đã cấu hình) ----------


@pytest.mark.integration
@pytest.mark.skipif(
    not _supabase_configured, reason="Chưa cấu hình Supabase Storage (.env)"
)
def test_supabase_storage_roundtrip():
    s = SupabaseStorage(
        os.environ["SUPABASE_TEST_URL"],
        os.environ["SUPABASE_TEST_SERVICE_KEY"],
        os.environ["SUPABASE_TEST_BUCKET"],
    )
    key = f"pytest/{uuid.uuid4().hex}/roundtrip.txt"
    try:
        s.save(key, b"hello-supabase")
        assert s.read(key) == b"hello-supabase"
    finally:
        s.delete(key)
