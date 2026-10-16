"""HTTP pool và xác thực Drive chỉ đọc. Không có thao tác ghi/xóa trên Drive."""

import asyncio
import json
from pathlib import Path

import httpx
from fastapi import HTTPException

from app.config import get_settings

_client: httpx.AsyncClient | None = None
_credentials = None
_credential_source: tuple[str, int] | None = None
_token_lock = asyncio.Lock()


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30, connect=10),
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
            follow_redirects=False,
            headers={"Accept-Encoding": "identity"},
        )
    return _client


async def headers(resource_key: str | None = None, file_id: str = "") -> dict[str, str]:
    global _credentials, _credential_source
    settings = get_settings()
    result = {}
    if settings.google_drive_service_account_file:
        try:
            path = Path(settings.google_drive_service_account_file)
            source = (str(path.resolve()), path.stat().st_mtime_ns)
            async with _token_lock:
                if source != _credential_source:
                    from google.oauth2.service_account import Credentials

                    info = json.loads(
                        await asyncio.to_thread(path.read_text, encoding="utf-8")
                    )
                    if info.get("token_uri") != "https://oauth2.googleapis.com/token":
                        raise ValueError("Unsupported token endpoint")
                    _credentials = await asyncio.to_thread(
                        Credentials.from_service_account_info,
                        info,
                        scopes=["https://www.googleapis.com/auth/drive.readonly"],
                    )
                    _credential_source = source
                if not _credentials.valid:
                    from google.auth.transport.requests import Request

                    await asyncio.to_thread(_credentials.refresh, Request())
                result["Authorization"] = "Bearer " + _credentials.token
        except Exception:
            raise HTTPException(503, "Kết nối kho tư liệu chưa sẵn sàng") from None
    elif settings.google_drive_api_key:
        result["X-Goog-Api-Key"] = settings.google_drive_api_key
    else:
        raise HTTPException(503, "Chưa cấu hình kho tư liệu")
    if resource_key and file_id:
        result["X-Goog-Drive-Resource-Keys"] = f"{file_id}/{resource_key}"
    return result


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
