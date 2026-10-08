import jwt
import pytest

from app.services.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret")
    assert hashed != "s3cret"
    assert verify_password("s3cret", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip():
    token = create_access_token("42")
    assert decode_token(token)["sub"] == "42"


def test_jwt_rejects_tampered_token():
    token = create_access_token("42")
    with pytest.raises(jwt.PyJWTError):
        decode_token(token + "x")
