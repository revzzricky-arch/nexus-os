"""
Approval and ToolCall Scoping Tests - Phase 2B-4 ownership boundary

Prove non-owner access denied at service boundary
"""

import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.models.user import User
from app.models.mission import Mission
from app.models.task import Task
from app.models.agent import Agent, AgentRun
from app.models.tool import ToolCall
from app.services.approval import approval_service
from app.services.tool_call import tool_call_service
from app.core.exceptions import PermissionDeniedError, NotFoundError
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
        owner_user = User(id=uuid.uuid4(), email="owner@example.com")
        other_user = User(id=uuid.uuid4(), email="other@example.com")
        session.add(owner_user)
        session.add(other_user)
        mission = Mission(id=uuid.uuid4(), title="Test", goal="Test", status="running", template="general", user_id=owner_user.id)
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
        tool_call = ToolCall(id=uuid.uuid4(), task_id=task.id, agent_run_id=run.id, tool_id="web_search", args={"query": "test"}, status="success", result={"results": []})
        session.add(tool_call)
        await session.flush()
        orphan_tool_call = ToolCall(id=uuid.uuid4(), tool_id="web_search", args={"query": "orphan"}, status="success", result={"results": []})
        session.add(orphan_tool_call)
        await session.commit()
        yield session


@pytest.mark.asyncio
async def test_non_owner_approval_access_denied(async_session: AsyncSession):
    from sqlalchemy import select
    from app.models.tool import Approval
    result = await async_session.execute(select(Approval).limit(1))
    approval = result.scalars().first()

    dev_context = {"user_id": "dev-user"}
    fetched = await approval_service.get_approval(async_session, approval.id, user_context=dev_context)
    assert fetched is not None

    other_user_id = uuid.uuid4()
    other_context = {"user_id": str(other_user_id)}
    with pytest.raises(PermissionDeniedError):
        await approval_service.get_approval(async_session, approval.id, user_context=other_context)

    anon_context = {"user_id": "anonymous"}
    with pytest.raises(PermissionDeniedError):
        await approval_service.get_approval(async_session, approval.id, user_context=anon_context)


@pytest.mark.asyncio
async def test_non_owner_approval_list_denied_without_mission(async_session: AsyncSession):
    other_user_id = uuid.uuid4()
    other_context = {"user_id": str(other_user_id)}
    approvals, total = await approval_service.list_approvals(async_session, user_context=other_context)
    assert total == 0


@pytest.mark.asyncio
async def test_non_owner_tool_call_access_denied(async_session: AsyncSession):
    from sqlalchemy import select
    all_tcs = await async_session.execute(select(ToolCall))
    tcs = list(all_tcs.scalars().all())
    linked_tc = None
    for tc in tcs:
        if tc.task_id is not None:
            linked_tc = tc
            break
    assert linked_tc is not None

    dev_context = {"user_id": "dev-user"}
    fetched = await tool_call_service.get_tool_call(async_session, linked_tc.id, user_context=dev_context)
    assert fetched is not None

    other_user_id = uuid.uuid4()
    other_context = {"user_id": str(other_user_id)}
    with pytest.raises(PermissionDeniedError):
        await tool_call_service.get_tool_call(async_session, linked_tc.id, user_context=other_context)


@pytest.mark.asyncio
async def test_orphan_tool_call_missing_linkage_fail_closed_for_non_dev(async_session: AsyncSession):
    from sqlalchemy import select
    all_tcs = await async_session.execute(select(ToolCall))
    tcs = list(all_tcs.scalars().all())
    orphan_tc = None
    for tc in tcs:
        if tc.task_id is None and tc.agent_run_id is None:
            orphan_tc = tc
            break
    assert orphan_tc is not None

    dev_context = {"user_id": "dev-user"}
    fetched = await tool_call_service.get_tool_call_scoped(async_session, orphan_tc.id, user_context=dev_context)
    assert fetched is not None

    other_user_id = uuid.uuid4()
    other_context = {"user_id": str(other_user_id)}
    with pytest.raises(PermissionDeniedError) as exc:
        await tool_call_service.get_tool_call_scoped(async_session, orphan_tc.id, user_context=other_context)
    assert "Missing mission linkage" in str(exc.value) or "fail closed" in str(exc.value)


@pytest.mark.asyncio
async def test_owner_access_allowed(async_session: AsyncSession):
    from sqlalchemy import select
    from app.models.mission import Mission
    mission_result = await async_session.execute(select(Mission).limit(1))
    mission = mission_result.scalars().first()
    owner_id = mission.user_id

    owner_context = {"user_id": str(owner_id)}
    from app.models.tool import Approval
    approval_result = await async_session.execute(select(Approval).limit(1))
    approval = approval_result.scalars().first()

    fetched = await approval_service.get_approval(async_session, approval.id, user_context=owner_context)
    assert fetched is not None
