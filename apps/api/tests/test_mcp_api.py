"""
MCP API Tests - Phase 2B-4
GET /mcp-servers, POST /mcp-servers, GET /mcp-servers/{id}/tools, DELETE /mcp-servers/{id}
+ SSE forbidden + secret reference + redaction
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.dependencies import get_db, get_current_user
from app.db.base import Base
from app.models.user import User
from app.services.mcp_manager import mcp_manager


@pytest.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine):
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        user = User(id=uuid.uuid4(), email="test@example.com")
        session.add(user)
        await session.flush()
        yield session


@pytest.fixture
def mock_user():
    return {"user_id": "dev-user", "token_valid": True}


@pytest.mark.asyncio
async def test_list_mcp_servers_api(async_session: AsyncSession, mock_user):
    async def override_get_db():
        yield async_session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/mcp-servers", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert "data" in resp.json()

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_mcp_server_api(async_session: AsyncSession, mock_user):
    async def override_get_db():
        yield async_session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/mcp-servers",
            json={"name": "test stdio", "transport": "stdio", "command": "python -m mcp_server"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "test stdio"

        resp2 = await client.post(
            "/api/v1/mcp-servers",
            json={"name": "private", "transport": "streamable_http", "url": "http://127.0.0.1:8000"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp2.status_code == 400

        resp_sse = await client.post(
            "/api/v1/mcp-servers",
            json={"name": "sse test", "transport": "sse_legacy", "url": "https://example.com/sse"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp_sse.status_code == 400
        assert "sse_legacy transport is disabled by default" in resp_sse.text

        resp_ref = await client.post(
            "/api/v1/mcp-servers",
            json={"name": "secret ref", "transport": "stdio", "command": "python -m server", "env": {"API_KEY": "${MY_SECRET}"}},
            headers={"Authorization": "Bearer test"},
        )
        assert resp_ref.status_code == 200
        data = resp_ref.json()["data"]
        assert data["env"]["API_KEY"] == "***REDACTED***"

        resp_raw_token = await client.post(
            "/api/v1/mcp-servers",
            json={"name": "raw token", "transport": "stdio", "command": "python -m server", "env": {"api_key": "sk-1234567890abcdef1234567890"}},
            headers={"Authorization": "Bearer test"},
        )
        assert resp_raw_token.status_code == 400

        resp_raw_pw = await client.post(
            "/api/v1/mcp-servers",
            json={"name": "raw pw", "transport": "stdio", "command": "python -m server", "env": {"password": "supersecret123"}},
            headers={"Authorization": "Bearer test"},
        )
        assert resp_raw_pw.status_code == 400

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_discover_mcp_tools_api(async_session: AsyncSession, mock_user):
    server = await mcp_manager.create_server(async_session, name="mock test server", transport="stdio", command="python -m mock")
    await async_session.commit()

    async def override_get_db():
        yield async_session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/mcp-servers/{server.id}/tools", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    app.dependency_overrides.clear()
