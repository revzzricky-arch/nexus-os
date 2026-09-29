"""
Tool Calls Tests - Phase 2B-4
lifecycle/permission integration/approval integration/event emission
"""

import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db.base import Base
from app.models.mission import Mission
from app.models.user import User
from app.models.task import Task
from app.models.agent import Agent, AgentRun
from app.services.tool_registry import tool_registry_service
from app.services.agent_runner import agent_runner_service
from app.services.event_bus import event_bus_service


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
        mission = Mission(id=uuid.uuid4(), title="Test Mission", goal="Test", status="running", template="general", user_id=user.id)
        session.add(mission)
        task = Task(id=uuid.uuid4(), mission_id=mission.id, title="Test Task", description="Test", status="running", agent_type="coder")
        session.add(task)
        agent = Agent(id=uuid.uuid4(), type="coder", role="Coder", system_prompt_template="test", model_config={}, tools=[], capability_tags=[])
        session.add(agent)
        await session.flush()
        agent_run = AgentRun(id=uuid.uuid4(), mission_id=mission.id, task_id=task.id, agent_id=agent.id, status="running")
        session.add(agent_run)
        await session.flush()
        yield session


@pytest.mark.asyncio
async def test_tool_call_lifecycle_auto(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)
    from sqlalchemy import select
    result = await async_session.execute(select(Mission).limit(1))
    mission = result.scalars().first()
    task_result = await async_session.execute(select(Task).limit(1))
    task = task_result.scalars().first()
    run_result = await async_session.execute(select(AgentRun).limit(1))
    run = run_result.scalars().first()

    # Low risk auto tool should succeed
    res = await agent_runner_service.execute_tool(
        async_session,
        mission_id=mission.id,
        task_id=task.id,
        agent_run_id=run.id,
        agent_type="researcher",
        tool_id="web_search",
        args={"query": "test"},
    )
    assert res["status"] == "success"
    assert "tool_call_id" in res

    # Check events emitted via direct query
    from app.models.event import Event
    result = await async_session.execute(select(Event).where(Event.mission_id == mission.id))
    events = list(result.scalars().all())
    tool_events = [e for e in events if e.type in ["tool_call_started", "tool_call_completed"]]
    assert len(tool_events) >= 2


@pytest.mark.asyncio
async def test_tool_call_requires_approval(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)
    result = await async_session.execute(select(Mission).limit(1))
    mission = result.scalars().first()
    task_result = await async_session.execute(select(Task).limit(1))
    task = task_result.scalars().first()
    run_result = await async_session.execute(select(AgentRun).limit(1))
    run = run_result.scalars().first()

    res = await agent_runner_service.execute_tool(
        async_session,
        mission_id=mission.id,
        task_id=task.id,
        agent_run_id=run.id,
        agent_type="coder",
        tool_id="shell",
        args={"command": "ls"},
    )
    assert res["status"] == "approval_required"
    assert "approval_id" in res
    assert res["permission_decision"]["requires_approval"] is True


@pytest.mark.asyncio
async def test_tool_call_denied_forbidden(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)
    from app.models.tool import ToolPermission
    perm = ToolPermission(id=uuid.uuid4(), tool_id="web_search", agent_type="researcher", permission="forbidden")
    async_session.add(perm)
    await async_session.flush()

    result = await async_session.execute(select(Mission).limit(1))
    mission = result.scalars().first()
    task_result = await async_session.execute(select(Task).limit(1))
    task = task_result.scalars().first()
    run_result = await async_session.execute(select(AgentRun).limit(1))
    run = run_result.scalars().first()

    res = await agent_runner_service.execute_tool(
        async_session,
        mission_id=mission.id,
        task_id=task.id,
        agent_run_id=run.id,
        agent_type="researcher",
        tool_id="web_search",
        args={"query": "test"},
    )
    assert res["status"] == "denied"


@pytest.mark.asyncio
async def test_approval_integration_execute_after_approved(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)
    result = await async_session.execute(select(Mission).limit(1))
    mission = result.scalars().first()
    task_result = await async_session.execute(select(Task).limit(1))
    task = task_result.scalars().first()
    run_result = await async_session.execute(select(AgentRun).limit(1))
    run = run_result.scalars().first()

    # Request shell -> approval required
    res = await agent_runner_service.execute_tool(
        async_session,
        mission_id=mission.id,
        task_id=task.id,
        agent_run_id=run.id,
        agent_type="coder",
        tool_id="shell",
        args={"command": "echo hello"},
    )
    assert res["status"] == "approval_required"
    approval_id = uuid.UUID(res["approval_id"])

    # Approve and execute
    from app.services.approval import approval_service
    await approval_service.decide_approval(async_session, approval_id=approval_id, decision="approved")

    exec_res = await agent_runner_service.handle_approval_decision(async_session, approval_id, "approved")
    assert exec_res["status"] in ["success", "failed"]  # success expected for echo
    assert exec_res["decision"] == "approved"
