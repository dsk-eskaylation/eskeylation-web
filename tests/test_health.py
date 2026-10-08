"""Test health endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _get(path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.get(path)


async def test_health_liveness():
    r = await _get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.integration
async def test_health_readiness_kiem_tra_db():
    r = await _get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}
