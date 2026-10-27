"""Validate fields consumed by public components while preserving legacy extras."""

import math
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.models.enums import ContentType


def validate_body_budget(body: dict) -> dict:
    """Bound work before recursive sanitizers, DB writes and JSON serialization."""
    pending = [(body, 0)]
    nodes = text_bytes = 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        if depth > 16 or nodes > 10_000:
            raise ValueError("Nội dung quá sâu hoặc có quá nhiều trường")
        if isinstance(value, dict):
            if len(value) + len(pending) > 10_000:
                raise ValueError("Nội dung có quá nhiều trường")
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError("Tên trường nội dung phải là chuỗi")
                text_bytes += len(key.encode("utf-8"))
                pending.append((item, depth + 1))
        elif isinstance(value, list):
            if len(value) + len(pending) > 10_000:
                raise ValueError("Nội dung có quá nhiều trường")
            pending.extend((item, depth + 1) for item in value)
        elif isinstance(value, str):
            text_bytes += len(value.encode("utf-8"))
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Nội dung không được chứa NaN hoặc Infinity")
        elif value is not None and not isinstance(value, (bool, int, float)):
            raise ValueError("Nội dung phải là dữ liệu JSON hợp lệ")
        if text_bytes > 1024 * 1024:
            raise ValueError("Nội dung vượt giới hạn 1 MB")
    return body


class Person(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    name: str
    media_id: int | None = None


class Credits(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    role: str
    members: list[Person] | None = None
    names: list[str] | None = None


FACEBOOK_HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com"}


def _https(url: str, hosts: set[str] | None = None) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("Link phải bắt đầu bằng https://")
    if hosts is not None and parts.hostname.lower() not in hosts:
        raise ValueError("Link sao kê phải là bài viết Facebook")
    return url.strip()


class Product(BaseModel):
    """Sản phẩm đang bán; không có tên -> trang hiện 'Hiện không có sản phẩm nào'."""

    model_config = ConfigDict(strict=True, extra="allow")
    name: str | None = None
    description: str | None = None
    form_url: str | None = None
    media_id: int | None = None

    @field_validator("form_url")
    @classmethod
    def _form_url(cls, value: str | None) -> str | None:
        return _https(value) if value else None


class Support(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    intro: str | None = None
    amount: str | None = None
    used: str | None = None
    qr_media_id: int | None = None
    statements: list[str] | None = None

    @field_validator("statements")
    @classmethod
    def _statements(cls, value: list[str] | None) -> list[str] | None:
        return [_https(url, FACEBOOK_HOSTS) for url in value] if value else value


class HomepageBody(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    intro: str | None = None
    maintain: list[str] | None = None
    leader: Person | None = None
    credits: list[Credits] | None = None
    sections: list[dict] | None = None
    community_intro: str | None = None
    community_rules: str | None = None
    product: Product | None = None
    support: Support | None = None


def validate_content_body(type_: ContentType, body: dict) -> None:
    if type_ == ContentType.homepage:
        try:
            HomepageBody.model_validate(body)
        except ValidationError as error:
            link = next((e for e in error.errors() if "Link" in e["msg"]), None)
            detail = link["msg"].removeprefix("Value error, ") if link else None
            raise HTTPException(
                422, detail or "Dữ liệu Trang chủ sai định dạng"
            ) from None
