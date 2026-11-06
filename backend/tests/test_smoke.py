"""
Smoke tests — verify the app starts and the health check works.
No database or OpenAI access needed: httpx's ASGITransport doesn't run
the lifespan hook, so init_db() is never called.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture
async def client():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_type(client):
    response = await client.post(
        "/api/v1/documents/upload",
        files=[("files", ("malware.exe", b"MZ...", "application/octet-stream"))],
    )
    assert response.status_code == 415
