import pytest

from scripts.nginx_security import INCLUDE, secure_config


def test_headers_cover_static_and_proxy_locations_and_other_domains_untouched():
    other = "server { server_name other.example; location / { return 200; } }"
    site = """server {
        server_name eskaylation.com www.eskaylation.com;
        location / { try_files $uri /index.html; }
        location /assets/ { add_header Cache-Control "public"; }
        location /api/ { proxy_pass http://127.0.0.1:8000; }
    }"""
    secured = secure_config(other + site)
    assert secured.startswith(other)
    assert secured.count(INCLUDE) == 4
    assert secure_config(secured) == secured
    assert 'add_header Cache-Control "public";' in secured


def test_quoted_braces_and_comments_do_not_break_block_detection():
    site = """# server { fake }
    server { server_name eskaylation.com;
        location / { return 200 "{safe}"; }
    }"""
    assert secure_config(site).count(INCLUDE) == 2


@pytest.mark.parametrize("text", ["server {", "server {server_name other.example;}"])
def test_invalid_or_unrelated_configuration_is_rejected(text):
    with pytest.raises(ValueError):
        secure_config(text)
