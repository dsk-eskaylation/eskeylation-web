"""Nén response văn bản; không nén lại stream Range hoặc ảnh đã tối ưu."""

from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


class TextCompression:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.compressed = GZipMiddleware(app, minimum_size=1000, compresslevel=5)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        target = (
            self.app
            if path.startswith(("/api/library/", "/media/", "/assets/"))
            else self.compressed
        )
        await target(scope, receive, send)
