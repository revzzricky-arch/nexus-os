"""
Approval API Tests - Phase 2B-4
GET /approvals, GET /approvals/{id}, POST /approvals/{id}/decision, GET /tool-calls/{id}
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.dependencies import get_db, get_current_user
from app.db.base import Base
from app.models.user import User
from app.models.mission import Mission
from app.models.task import Task
from app.models.agent import Agent, AgentRun
from app.services.tool_registry import tool_registry_service
from app.services.approval import approval_service


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
        mission = Mission(id=uuid.uuid4(), title="Test", goal="Test", status="running", template="general", user_id=user.id)
        session.add(mission)
        task = Task(id=uuid.uuid4(), mission_id=mission.id, title="Test Task", description="Test", status="running", agent_type="coder")
        session.add(task)
        agent = Agent(id=uuid.uuid4(), type="coder", role="Coder", system_prompt_template="test", model_config={}, tools=[], capability_tags=[])
        session.add(agent)
        await session.flush()
        run = AgentRun(id=uuid.uuid4(), mission_id=mission.id, task_id=task.id, agent_id=agent.id, status="running")
        session.add(run)
        await session.flush()
        await tool_registry_service.seed_builtin_tools(session)
        approval = await approval_service.create_approval(session, mission_id=mission.id, task_id=task.id, agent_run_id=run.id, requested_payload={"tool_id": "shell"})
        await session.commit()
        yield session


@pytest.fixture
def mock_user():
    return {"user_id": "dev-user", "token_valid": True}


@pytest.mark.asyncio
async def test_list_approvals_api(async_session: AsyncSession, mock_user):
    async def override_get_db():
        yield async_session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/approvals", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert data["total"] >= 1

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_approval_api(async_session: AsyncSession, mock_user):
    from sqlalchemy import select
    result = await async_session.execute(select(__import__("app.models.tool", fromlist=["Approval"]).Approval).limit(1))
    approval = result.scalars().first()
    approval_id = approval.id

    async def override_get_db():
        yield async_session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/approvals/{approval_id}", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == str(approval_id)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_decide_approval_api(async_session: AsyncSession, mock_user):
    from sqlalchemy import select
    from app.models.tool import Approval
    result = await async_session.execute(select(Approval).limit(1))
    approval = result.scalars().first()
    approval_id = approval.id

    async def override_get_db():
        yield async_session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            json={"decision": "approved", "review_comment": "ok"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "approved"

    app.dependency_overrides.clear()
