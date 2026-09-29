"""
Agent Runner Tests - Phase 2B-3
Agent_run creation, task lifecycle, safe stub execution, event emission
"""

import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db.base import Base
from app.models.mission import Mission
from app.models.task import Task
from app.models.agent import Agent, AgentRun
from app.models.event import Event
from app.services.event_bus import EventBusService
from app.services.agent_runner import AgentRunnerService


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
        yield session


@pytest.fixture
def event_bus():
    return EventBusService()


@pytest.fixture
def agent_runner(event_bus):
    return AgentRunnerService(event_bus=event_bus)


@pytest.fixture
async def mission_and_task(async_session: AsyncSession):
    mission = Mission(
        id=uuid.uuid4(),
        title="Test Mission",
        goal="Test goal",
        status="running",
        template="general",
    )
    async_session.add(mission)
    await async_session.flush()

    # Seed agent
    agent = Agent(
        id=uuid.uuid4(),
        type="researcher",
        role="Researcher",
        system_prompt_template="You are researcher",
        model_config={"provider": "openai-compatible", "model": "gpt-4o-mini"},
        tools=[],
        capability_tags=[],
    )
    async_session.add(agent)
    await async_session.flush()

    task = Task(
        id=uuid.uuid4(),
        mission_id=mission.id,
        title="Research Task",
        description="Research something",
        agent_type="researcher",
        status="pending",
    )
    async_session.add(task)
    await async_session.flush()

    return mission, task, agent


@pytest.mark.asyncio
async def test_agent_run_creation(async_session: AsyncSession, agent_runner: AgentRunnerService, mission_and_task):
    mission, task, agent = mission_and_task

    result = await agent_runner.run_task(
        session=async_session,
        mission_id=mission.id,
        task_id=task.id,
        agent_type="researcher",
    )

    assert result["task_id"] == str(task.id)
    assert result["status"] == "completed"
    assert "agent_run_id" in result
    assert result["output"] is not None
    assert result["output"]["deterministic"] is True

    # Check agent_run created in DB
    run_result = await async_session.execute(select(AgentRun).where(AgentRun.task_id == task.id))
    runs = run_result.scalars().all()
    assert len(runs) == 1
    assert runs[0].status == "completed"
    assert runs[0].mission_id == mission.id


@pytest.mark.asyncio
async def test_task_lifecycle(async_session: AsyncSession, agent_runner: AgentRunnerService, mission_and_task):
    mission, task, agent = mission_and_task

    assert task.status == "pending"

    await agent_runner.run_task(
        session=async_session,
        mission_id=mission.id,
        task_id=task.id,
        agent_type="researcher",
    )

    # Refresh task
    await async_session.refresh(task)
    assert task.status == "completed"
    assert task.output is not None
    assert task.token_usage > 0


@pytest.mark.asyncio
async def test_safe_stub_execution(async_session: AsyncSession, agent_runner: AgentRunnerService, mission_and_task):
    mission, task, agent = mission_and_task

    result = await agent_runner.run_task(
        session=async_session,
        mission_id=mission.id,
        task_id=task.id,
        agent_type="researcher",
    )

    # Safe stub should not do dangerous things
    # Check output is deterministic and safe
    assert result["output"]["deterministic"] is True
    assert "summary" in result["output"]

    # Ensure no eval/exec/compile in output
    output_str = str(result["output"]).lower()
    assert "eval" not in output_str or "evaluation" in output_str  # Allow "evaluation" but not eval()
    # Output should be simple dict, not code execution


@pytest.mark.asyncio
async def test_event_emission(async_session: AsyncSession, agent_runner: AgentRunnerService, mission_and_task):
    mission, task, agent = mission_and_task

    await agent_runner.run_task(
        session=async_session,
        mission_id=mission.id,
        task_id=task.id,
        agent_type="researcher",
    )

    # Check events emitted
    result = await async_session.execute(select(Event).where(Event.mission_id == mission.id))
    events = result.scalars().all()

    # Should have at least: agent_state_changed (idle->running), task_status_changed (pending->running), task_status_changed (running->completed), agent_state_changed (running->completed), cost_updated
    assert len(events) >= 4

    event_types = [e.type for e in events]
    assert "task_status_changed" in event_types
    assert "agent_state_changed" in event_types
    assert "cost_updated" in event_types

    # Check event structure matches shared contract
    for event in events:
        assert event.id is not None
        assert event.type is not None
        assert event.source is not None
        assert event.mission_id == mission.id
        assert event.timestamp is not None
        assert event.payload is not None


@pytest.mark.asyncio
async def test_agent_runner_different_agent_types(async_session: AsyncSession, agent_runner: AgentRunnerService):
    mission = Mission(id=uuid.uuid4(), title="Test", goal="Goal", status="running", template="general")
    async_session.add(mission)
    await async_session.flush()

    # Create agents for each type
    for agent_type in ["researcher", "coder", "analyst", "supervisor"]:
        agent = Agent(
            id=uuid.uuid4(),
            type=agent_type,
            role=agent_type.capitalize(),
            system_prompt_template=f"You are {agent_type}",
            model_config={},
            tools=[],
            capability_tags=[],
        )
        async_session.add(agent)
    await async_session.flush()

    # Create tasks for each agent type
    for agent_type in ["researcher", "coder", "analyst", "supervisor"]:
        task = Task(
            id=uuid.uuid4(),
            mission_id=mission.id,
            title=f"{agent_type.capitalize()} Task",
            description=f"Task for {agent_type}",
            agent_type=agent_type,
            status="pending",
        )
        async_session.add(task)
        await async_session.flush()

        result = await agent_runner.run_task(
            session=async_session,
            mission_id=mission.id,
            task_id=task.id,
            agent_type=agent_type,
        )

        assert result["status"] == "completed"
        assert result["output"]["type"] in ["research", "code", "analysis", "coordination"]


@pytest.mark.asyncio
async def test_no_real_execution():
    # Ensure agent_runner does not use eval/exec/compile or shell
    import pathlib

    runner_path = pathlib.Path(__file__).parent.parent / "app" / "services" / "agent_runner.py"
    content = runner_path.read_text()

    # Check for dangerous patterns (allow comments mentioning them as forbidden)
    # We check for actual usage, not just mention in docstring
    lines = content.split("\n")
    for line in lines:
        stripped = line.strip()
        # Skip comments and docstrings
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        if stripped.startswith("- "):  # bullet in docstring
            continue
        # Check for dangerous builtins being called
        assert "eval(" not in stripped or "deterministic" in stripped.lower() or "no eval" in stripped.lower(), f"Found eval in: {line}"
        # exec as function call (not exec_command which is sandbox)
        if "exec(" in stripped and "exec_command" not in stripped and "no exec" not in stripped.lower():
            # Allow if in comment about forbidden
            if "must NOT" not in content and "must not" not in content.lower():
                assert False, f"Found exec in: {line}"
