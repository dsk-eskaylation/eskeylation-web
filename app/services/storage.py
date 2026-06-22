from abc import ABC, abstractmethod
from pathlib import Path

from app.config import get_settings


class Storage(ABC):
    """Interface lưu trữ media. Mọi truy cập media đi qua đây.

    Phase 0 dùng LocalStorage cho dev; Phase 9 thêm SupabaseStorage
    mà không phải sửa service/router gọi đến interface này.
    """

    @abstractmethod
    def save(self, key: str, data: bytes) -> str:
        """Lưu nội dung theo key, trả về URL truy cập."""

    @abstractmethod
    def url(self, key: str) -> str:
        """Trả về URL ổn định cho key."""


class LocalStorage(Storage):
    """Lưu file xuống thư mục cục bộ (chỉ dùng cho dev)."""

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def save(self, key: str, data: bytes) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.url(key)

    def url(self, key: str) -> str:
        return f"/{self.root.as_posix()}/{key}"


def get_storage() -> Storage:
    return LocalStorage(get_settings().media_root)
