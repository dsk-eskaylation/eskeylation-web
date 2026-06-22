from math import ceil

from pydantic import BaseModel, computed_field


class Page[T](BaseModel):
    """Trang kết quả phân trang. `pages` được tính và trả ra response."""

    items: list[T]
    total: int
    page: int
    page_size: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pages(self) -> int:
        return ceil(self.total / self.page_size) if self.page_size else 0

    @classmethod
    def create(cls, items: list[T], total: int, page: int, page_size: int) -> "Page[T]":
        return cls(items=items, total=total, page=page, page_size=page_size)
