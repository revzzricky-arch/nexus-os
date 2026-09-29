"""
Tool API Tests - Phase 2B-4
GET /api/v1/tools, GET /tools/{tool_id}, GET /tool-calls/{id}
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.dependencies import get_db, get_current_user
from app.db.base import Base
from app.models.user import User
from app.services.tool_registry import tool_registry_service


@pytest.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    try:
        await engine.dispose()
    except Exception:
        pass


@pytest.fixture
async def async_session(async_engine):
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        user = User(id=uuid.uuid4(), email="test@example.com")
        session.add(user)
        await session.flush()
        await tool_registry_service.seed_builtin_tools(session)
        await session.commit()
        yield session


@pytest.fixture
def mock_user():
    return {"user_id": "dev-user", "token_valid": True}


@pytest.mark.asyncio
async def test_list_tools_api(async_session: AsyncSession, mock_user):
    async def override_get_db():
        yield async_session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/tools", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert data["total"] >= 6
        ids = [t["id"] for t in data["data"]]
        assert "web_search" in ids
        assert "shell" in ids

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_tool_api(async_session: AsyncSession, mock_user):
    async def override_get_db():
        yield async_session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/tools/web_search", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == "web_search"

        resp2 = await client.get("/api/v1/tools/nonexistent", headers={"Authorization": "Bearer test"})
        assert resp2.status_code == 404

    app.dependency_overrides.clear()
