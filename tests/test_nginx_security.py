import pytest

from scripts.nginx_security import INCLUDE, secure_config, streaming_upload_config


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


@pytest.mark.parametrize(
    "existing", ["", "proxy_request_buffering on;", "proxy_request_buffering off;"]
)
def test_upload_streaming_changes_only_production_api_proxy(existing):
    other = (
        "server { server_name other.example; location /api { "
        "proxy_pass http://127.0.0.1:8000; } }"
    )
    site = """server {
        server_name eskaylation.com;
        listen 443 ssl;
        location / { try_files $uri /index.html; }
        location ~ ^/(api|auth|admin)/ {
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            EXISTING
        }
    }""".replace("EXISTING", existing)
    secured = streaming_upload_config(other + site)
    assert secured.startswith(other)
    assert secured.count("proxy_request_buffering off;") == 1
    assert "proxy_request_buffering on;" not in secured
    assert 'proxy_set_header Connection "upgrade";' in secured
    assert "listen 443 ssl;" in secured
    assert streaming_upload_config(secured) == secured


def test_upload_streaming_rejects_unsafe_upstream_protocol_or_unknown_proxy():
    with pytest.raises(ValueError):
        streaming_upload_config(
            "server { server_name eskaylation.com; location /admin { "
            "proxy_pass http://127.0.0.1:8000; } }"
        )
