"""S3 contract tests with Stubber: no network, credentials or production writes."""

import io

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import Stubber
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.services import storage
from app.services.storage import S3Storage, get_storage

BUCKET = "test-eskaylation-media"
CDN = "https://test.cloudfront.net"


@pytest.fixture
def s3(monkeypatch):
    client = boto3.client(
        "s3",
        region_name="ap-southeast-2",
        aws_access_key_id="isolated-test-key",
        aws_secret_access_key="isolated-test-secret",
    )
    monkeypatch.setattr(storage, "_s3_client", lambda region: client)
    with Stubber(client) as stubber:
        yield S3Storage(BUCKET, "ap-southeast-2", CDN), stubber
        stubber.assert_no_pending_responses()
    client.close()


def test_s3_private_roundtrip_and_url_encoding(s3):
    backend, stubber = s3
    key = "music/Bài hát #1%?.mp3"
    full_key = "cms/" + key
    data = b"isolated test audio"
    stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": BUCKET,
            "Key": full_key,
            "Body": data,
            "ContentType": "audio/mpeg",
            "ServerSideEncryption": "AES256",
            "CacheControl": "public, max-age=300",
            "IfNoneMatch": "*",
        },
    )
    raw_body = io.BytesIO(data)
    response_body = StreamingBody(raw_body, len(data))
    stubber.add_response(
        "get_object",
        {"Body": response_body},
        {"Bucket": BUCKET, "Key": full_key},
    )
    stubber.add_response("delete_object", {}, {"Bucket": BUCKET, "Key": full_key})
    expected = CDN + "/cms/music/B%C3%A0i%20h%C3%A1t%20%231%25%3F.mp3"
    assert backend.save(key, data) == expected
    assert backend.read(key) == data
    assert raw_body.closed
    backend.delete(key)


def test_s3_access_denied_propagates_without_local_fallback(s3):
    backend, stubber = s3
    stubber.add_client_error(
        "delete_object",
        service_error_code="AccessDenied",
        http_status_code=403,
        expected_params={"Bucket": BUCKET, "Key": "cms/file.mp3"},
    )
    with pytest.raises(ClientError):
        backend.delete("file.mp3")


def test_cdn_urls_never_resolve_credentials(monkeypatch):
    def unexpected_network(region):
        pytest.fail("Serializing a CDN URL must not initialize an SDK client")

    monkeypatch.setattr(storage, "_s3_client", unexpected_network)
    monkeypatch.setattr(get_settings(), "storage_backend", "s3")
    monkeypatch.setattr(get_settings(), "s3_bucket", BUCKET)
    monkeypatch.setattr(get_settings(), "s3_cdn_url", CDN)
    assert get_storage().url("track.mp3") == CDN + "/cms/track.mp3"


@pytest.mark.parametrize(
    "key", ["", "/outside.mp3", "../outside.mp3", "a/../b", "a//b", "a\\b", "a\nb"]
)
def test_s3_rejects_ambiguous_keys_before_sdk_access(key, s3):
    backend, _ = s3
    with pytest.raises(ValueError):
        backend.save(key, b"test")
    with pytest.raises(ValueError):
        backend.delete(key)


@pytest.mark.parametrize(
    ("bucket", "region", "cdn"),
    [
        ("", "ap-southeast-2", CDN),
        (BUCKET, "ap-southeast-2-an", CDN),
        (BUCKET, "ap-southeast-2", "http://test.cloudfront.net"),
        (BUCKET, "ap-southeast-2", "https://user:secret@test.cloudfront.net"),
        (BUCKET, "ap-southeast-2", CDN + "?secret=value"),
        (BUCKET, "ap-southeast-2", CDN + "/music"),
    ],
)
def test_incomplete_or_unsafe_s3_configuration_is_rejected(bucket, region, cdn):
    with pytest.raises(ValueError):
        S3Storage(bucket, region, cdn)


def test_unknown_storage_backend_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, storage_backend="s33")
