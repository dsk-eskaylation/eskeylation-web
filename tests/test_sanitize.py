"""Unit test sanitize/embed (thuần, không cần DB)."""

import pytest
from fastapi import HTTPException

from app.services.sanitize import (
    music_source,
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
    ("url", "provider", "player"),
    [
        (
            "https://soundcloud.com/sdrecords-vn/dsk-lon-roi",
            "soundcloud",
            "https://w.soundcloud.com/player/?url=https%3A%2F%2Fsoundcloud.com"
            "%2Fsdrecords-vn%2Fdsk-lon-roi&auto_play=true&visual=false"
            "&show_comments=false",
        ),
        (
            "https://m.soundcloud.com/da_sun_kid/co-sao-dau-dsk?si=abc",
            "soundcloud",
            "https://w.soundcloud.com/player/?url=https%3A%2F%2Fsoundcloud.com"
            "%2Fda_sun_kid%2Fco-sao-dau-dsk&auto_play=true&visual=false"
            "&show_comments=false",
        ),
        (
            "https://www.youtube.com/watch?v=IdU2YDea9d0",
            "youtube",
            "https://www.youtube.com/embed/IdU2YDea9d0?autoplay=1",
        ),
        (
            "https://youtu.be/IdU2YDea9d0",
            "youtube",
            "https://www.youtube.com/embed/IdU2YDea9d0?autoplay=1",
        ),
        (
            "https://vimeo.com/76979871",
            "vimeo",
            "https://player.vimeo.com/video/76979871?autoplay=1",
        ),
    ],
)
def test_music_source_builds_player_url(url, provider, player):
    assert music_source(url) == (provider, player)


@pytest.mark.parametrize(
    "url",
    [
        "https://soundcloud.com/sdrecords-vn",
        "ftp://soundcloud.com/a/b",
        "https://soundcloud.com.evil.com/a/b",
        "https://evil.com/soundcloud.com/a/b",
        None,
    ],
)
def test_music_source_rejects_non_track_links(url):
    assert music_source(url) is None
