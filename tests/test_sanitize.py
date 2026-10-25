"""Unit test sanitize/embed (thuần, không cần DB)."""

import pytest
from fastapi import HTTPException

from app.services.sanitize import (
    playable_music_embed,
    sanitize_body,
    sanitize_html,
    sanitize_summary,
    validate_embeds,
)


def test_sanitize_summary_bo_het_tag():
    out = sanitize_summary("Hello <b>x</b><script>alert(1)</script>")
    assert "<" not in out
    assert "<script" not in out


def test_sanitize_summary_none():
    assert sanitize_summary(None) is None


def test_sanitize_html_giu_tag_an_toan_bo_script():
    out = sanitize_html("<p>ok</p><script>alert(1)</script>")
    assert "<p>ok</p>" in out
    assert "<script" not in out


def test_sanitize_html_bo_event_handler():
    out = sanitize_html('<a href="x" onclick="evil()">link</a>')
    assert "onclick" not in out
    assert "href" in out


def test_sanitize_body_de_quy():
    body = {
        "desc": "<script>x</script><b>hi</b>",
        "nested": {"t": "<iframe src='x'></iframe>safe"},
        "list": ["<script>a</script>b"],
        "num": 5,
    }
    out = sanitize_body(body)
    assert "<script" not in out["desc"] and "<b>hi</b>" in out["desc"]
    assert "<iframe" not in out["nested"]["t"]
    assert "<script" not in out["list"][0]
    assert out["num"] == 5


def test_validate_embeds_cho_phep_youtube():
    validate_embeds({"embed_url": "https://www.youtube.com/watch?v=abc"})


def test_validate_embeds_chan_host_la():
    with pytest.raises(HTTPException) as exc:
        validate_embeds({"embed_url": "https://evil.com/x"})
    assert exc.value.status_code == 422


def test_validate_embeds_chan_ip_noi_bo():
    with pytest.raises(HTTPException):
        validate_embeds({"video_url": "http://169.254.169.254/latest/meta-data"})


def test_validate_embeds_khong_co_key_ok():
    validate_embeds({"title": "không có embed"})


@pytest.mark.parametrize(
    "url",
    [
        "https://soundcloud.com/sdrecords-vn/dsk-lon-roi",
        "https://m.soundcloud.com/da_sun_kid/co-sao-dau-dsk",
        "https://www.youtube.com/watch?v=IdU2YDea9d0",
        "https://youtu.be/IdU2YDea9d0",
    ],
)
def test_playable_music_embed_nhan_soundcloud_va_youtube(url):
    assert playable_music_embed(url)
    validate_embeds({"embed_url": url})


@pytest.mark.parametrize(
    "url",
    [
        "https://soundcloud.com/sdrecords-vn",  # trang người dùng, không phải bài
        "ftp://soundcloud.com/a/b",
        "https://soundcloud.com.evil.com/a/b",
        "https://evil.com/soundcloud.com/a/b",
        None,
    ],
)
def test_playable_music_embed_chan_link_khong_phai_bai(url):
    assert not playable_music_embed(url)
