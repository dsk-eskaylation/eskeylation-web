"""Validate fields consumed by public components while preserving legacy extras."""

import math

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError

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


class HomepageBody(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    intro: str | None = None
    maintain: list[str] | None = None
    leader: Person | None = None
    credits: list[Credits] | None = None
    sections: list[dict] | None = None


def validate_content_body(type_: ContentType, body: dict) -> None:
    if type_ == ContentType.homepage:
        try:
            HomepageBody.model_validate(body)
        except ValidationError:
            raise HTTPException(422, "Dữ liệu Trang chủ sai định dạng") from None
