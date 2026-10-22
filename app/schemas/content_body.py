"""Validate fields consumed by public components while preserving legacy extras."""

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError

from app.models.enums import ContentType


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
