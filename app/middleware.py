"""Bound request parsing and compress text without changing media streams."""

import json

from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class RequestBodyLimit:
    """Bound non-upload mutations before JSON/form decoding allocates large bodies."""

    limit = 1024 * 1024

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}
            or (
                scope["method"] == "POST"
                and scope.get("path", "").rstrip("/") == "/admin/media"
            )
        ):
            await self.app(scope, receive, send)
            return

        async def reject(status: int, detail: str) -> None:
            await JSONResponse(
                {"detail": detail},
                status_code=status,
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )(scope, receive, send)

        headers = dict(scope.get("headers", []))
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                length = int(declared)
            except ValueError:
                await reject(400, "Kích thước yêu cầu không hợp lệ")
                return
            if length < 0:
                await reject(400, "Kích thước yêu cầu không hợp lệ")
                return
            if length > self.limit:
                await reject(413, "Yêu cầu vượt giới hạn 1 MB")
                return
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.limit:
                await reject(413, "Yêu cầu vượt giới hạn 1 MB")
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        media_type = (
            headers.get(b"content-type", b"").partition(b";")[0].strip().lower()
        )
        if body and (
            not media_type
            or media_type == b"application/json"
            or media_type.endswith(b"+json")
        ):
            try:
                json.loads(body)
            except (ValueError, UnicodeError, RecursionError):
                await reject(400, "Dữ liệu JSON không hợp lệ")
                return
        replayed = False

        async def bounded_receive():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


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
