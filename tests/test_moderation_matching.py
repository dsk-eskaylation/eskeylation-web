"""Banned-word matching must survive NFD input and respect word boundaries."""

import unicodedata

from app.services.moderation import _compile, _find_hits

WORDS = _compile(["ngu", "đít", "lồn", "óc chó", "Địt mẹ"])


def nfd(text: str) -> str:
    return unicodedata.normalize("NFD", text)


def test_whole_words_only():
    assert _find_hits("người ngủ ngon, móc chó vào cổng", WORDS) == set()
    assert _find_hits("đồ ngu", WORDS) == {"ngu"}
    assert _find_hits("ÓC CHÓ thật", WORDS) == {"óc chó"}


def test_nfd_text_and_words_are_normalized():
    assert _find_hits(nfd("người Việt"), WORDS) == set()
    assert _find_hits(nfd("cái lồn"), WORDS) == {"lồn"}
    assert _find_hits(nfd("đít"), _compile([nfd("đít")])) == {"đít"}
    assert _find_hits("địt mẹ", WORDS) == {"địt mẹ"}
