"""
ApprovalService Tests - Phase 2B-4
create/list/approve/deny/expire/edited args/persistence
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.models.mission import Mission
from app.models.user import User
from app.services.approval import approval_service


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
        # Seed required mission
        user = User(id=uuid.uuid4(), email="test@example.com")
        session.add(user)
        mission = Mission(id=uuid.uuid4(), title="Test Mission", goal="Test", status="running", template="general", user_id=user.id)
        session.add(mission)
        await session.flush()
        yield session


@pytest.mark.asyncio
async def test_create_approval(async_session: AsyncSession):
    result = await async_session.execute(__import__("sqlalchemy").select(Mission).limit(1))
    mission = result.scalars().first()
    mission_id = mission.id

    approval = await approval_service.create_approval(
        async_session,
        mission_id=mission_id,
        type="tool",
        requested_by="coder",
        requested_payload={"tool_id": "shell", "args": {"command": "ls"}, "risk_level": "critical"},
    )
    assert approval.id is not None
    assert approval.status == "pending"
    assert approval.mission_id == mission_id
    assert approval.requested_payload["tool_id"] == "shell"


@pytest.mark.asyncio
async def test_list_approvals(async_session: AsyncSession):
    from sqlalchemy import select
    result = await async_session.execute(select(Mission).limit(1))
    mission = result.scalars().first()
    mission_id = mission.id

    await approval_service.create_approval(async_session, mission_id=mission_id, requested_payload={"tool_id": "shell"})
    await approval_service.create_approval(async_session, mission_id=mission_id, requested_payload={"tool_id": "write_file"})

    approvals, total = await approval_service.list_approvals(async_session, mission_id=mission_id)
    assert total >= 2
    assert len(approvals) >= 2


@pytest.mark.asyncio
async def test_approve_approval(async_session: AsyncSession):
    from sqlalchemy import select
    result = await async_session.execute(select(Mission).limit(1))
    mission = result.scalars().first()

    approval = await approval_service.create_approval(async_session, mission_id=mission.id, requested_payload={"tool_id": "shell"})

    decided = await approval_service.decide_approval(async_session, approval_id=approval.id, decision="approved", review_comment="ok")
    assert decided.status == "approved"
    assert decided.review_comment == "ok"
    assert decided.reviewed_at is not None


@pytest.mark.asyncio
async def test_deny_approval(async_session: AsyncSession):
    from sqlalchemy import select
    result = await async_session.execute(select(Mission).limit(1))
    mission = result.scalars().first()

    approval = await approval_service.create_approval(async_session, mission_id=mission.id, requested_payload={"tool_id": "shell"})

    decided = await approval_service.decide_approval(async_session, approval_id=approval.id, decision="denied", review_comment="not allowed")
    assert decided.status == "denied"


@pytest.mark.asyncio
async def test_expire_approval(async_session: AsyncSession):
    from sqlalchemy import select
    result = await async_session.execute(select(Mission).limit(1))
    mission = result.scalars().first()

    # Create expired approval
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    approval = await approval_service.create_approval(async_session, mission_id=mission.id, requested_payload={"tool_id": "shell"}, expires_at=past)

    # Try to decide should fail because expired
    from app.core.exceptions import ValidationError
    with pytest.raises(ValidationError):
        await approval_service.decide_approval(async_session, approval_id=approval.id, decision="approved")

    # Check status is expired
    fetched = await approval_service.get_approval(async_session, approval.id)
    assert fetched.status == "expired"


@pytest.mark.asyncio
async def test_edited_args(async_session: AsyncSession):
    from sqlalchemy import select
    result = await async_session.execute(select(Mission).limit(1))
    mission = result.scalars().first()

    approval = await approval_service.create_approval(async_session, mission_id=mission.id, requested_payload={"tool_id": "shell", "args": {"command": "rm -rf /"}})

    edited = {"command": "ls -la"}
    decided = await approval_service.decide_approval(async_session, approval_id=approval.id, decision="approved", edited_args=edited)
    assert decided.edited_args == edited
    assert decided.status == "approved"
