"""
PermissionService Tests - Phase 2B-4
forbidden/shell always approval/critical/high approval/low-risk auto/mission overrides/argument-level
"""

import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.models.tool import ToolPermission
from app.services.tool_registry import tool_registry_service
from app.services.permission import permission_service


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


@pytest.mark.asyncio
async def test_shell_always_approval(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)
    decision = await permission_service.evaluate(async_session, agent_type="coder", tool_id="shell", args={"command": "ls"}, mission_id=uuid.uuid4())
    assert decision.decision == "require_approval"
    assert decision.requires_approval is True
    assert "ALWAYS" in decision.reason or "always" in decision.reason.lower()


@pytest.mark.asyncio
async def test_critical_high_approval(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)
    # write_file is high risk
    decision = await permission_service.evaluate(async_session, agent_type="coder", tool_id="write_file", args={"path": "output/test.txt", "content": "hi"}, mission_id=uuid.uuid4())
    assert decision.decision == "require_approval"
    assert decision.risk_level == "high"

    # shell critical
    decision2 = await permission_service.evaluate(async_session, agent_type="coder", tool_id="shell", args={"command": "echo hi"})
    assert decision2.decision == "require_approval"
    assert decision2.risk_level == "critical"


@pytest.mark.asyncio
async def test_low_risk_auto(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)
    decision = await permission_service.evaluate(async_session, agent_type="researcher", tool_id="web_search", args={"query": "test"})
    assert decision.decision == "allow"
    assert decision.requires_approval is False

    decision2 = await permission_service.evaluate(async_session, agent_type="researcher", tool_id="read_file", args={"path": "output/test.txt"})
    assert decision2.decision == "allow"


@pytest.mark.asyncio
async def test_forbidden_denied(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)
    # Create forbidden permission
    perm = ToolPermission(
        id=uuid.uuid4(),
        tool_id="web_search",
        agent_type="researcher",
        permission="forbidden",
    )
    async_session.add(perm)
    await async_session.flush()

    decision = await permission_service.evaluate(async_session, agent_type="researcher", tool_id="web_search", args={"query": "test"})
    assert decision.decision == "deny"
    assert decision.permission == "forbidden"


@pytest.mark.asyncio
async def test_mission_overrides(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)
    mission_id = uuid.uuid4()

    # Mission policy override forbidden
    mission_policy = {"tool_permissions": {"web_search": "forbidden"}}
    decision = await permission_service.evaluate(async_session, agent_type="researcher", tool_id="web_search", args={"query": "test"}, mission_id=mission_id, mission_policy=mission_policy)
    assert decision.decision == "deny"

    # Mission override auto but shell still approval (cannot bypass)
    mission_policy2 = {"tool_permissions": {"shell": "auto"}}
    decision2 = await permission_service.evaluate(async_session, agent_type="coder", tool_id="shell", args={"command": "ls"}, mission_id=mission_id, mission_policy=mission_policy2)
    assert decision2.decision == "require_approval"
    assert decision2.requires_approval is True


@pytest.mark.asyncio
async def test_argument_level_rules(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)
    # Create arg pattern permission
    perm = ToolPermission(
        id=uuid.uuid4(),
        tool_id="read_file",
        agent_type="coder",
        permission="forbidden",
        arg_pattern={"path": "^/etc/.*"},
    )
    async_session.add(perm)
    await async_session.flush()

    # Should match and deny
    decision = await permission_service.evaluate(async_session, agent_type="coder", tool_id="read_file", args={"path": "/etc/passwd"})
    assert decision.decision == "deny"

    # Should not match, allow (low risk)
    decision2 = await permission_service.evaluate(async_session, agent_type="coder", tool_id="read_file", args={"path": "output/test.txt"})
    assert decision2.decision == "allow"
