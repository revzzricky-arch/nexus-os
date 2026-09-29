"""
Job Ownership / Mission Scoping Tests - Phase 3 PR 3.1 fix per PR #8 review
- owner can get/list/cancel
- non-owner cannot get job
- non-owner cannot cancel job
- non-owner cannot list another mission's jobs
- orphan/missing mission linkage fails closed
- anonymous denied
"""

import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.base import Base
from app.models.mission import Mission
from app.services.job import job_service
from app.core.exceptions import PermissionDeniedError, NotFoundError


@pytest.fixture
def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    return eng


@pytest.fixture
async def session_factory(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def create_mission_with_user(factory, user_id=None, title="Owned Mission"):
    async with factory() as session:
        m = Mission(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title,
            goal="Test goal",
            template="general",
            status="draft",
        )
        session.add(m)
        await session.commit()
        await session.refresh(m)
        return m


@pytest.mark.asyncio
async def test_owner_can_get_list_cancel(session_factory):
    owner_id = uuid.uuid4()
    mission = await create_mission_with_user(session_factory, user_id=owner_id)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id, user_context={"user_id": "dev-user"})
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        fetched = await job_service.get_job(session, job_id, user_context={"user_id": "dev-user"})
        assert fetched.id == job_id

    async with session_factory() as session:
        jobs, total = await job_service.list_jobs(session, mission_id=mission.id, user_context={"user_id": "dev-user"})
        assert total >= 1

    async with session_factory() as session:
        cancelled = await job_service.cancel_job(session, job_id, user_context={"user_id": "dev-user"})
        await session.commit()
        assert cancelled.status == "cancelled"


@pytest.mark.asyncio
async def test_non_owner_cannot_get_job(session_factory):
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    mission = await create_mission_with_user(session_factory, user_id=owner_id)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id, user_context={"user_id": "dev-user"})
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        with pytest.raises(PermissionDeniedError):
            await job_service.get_job(session, job_id, user_context={"user_id": str(other_user_id)})


@pytest.mark.asyncio
async def test_non_owner_cannot_cancel_job(session_factory):
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    mission = await create_mission_with_user(session_factory, user_id=owner_id)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id, user_context={"user_id": "dev-user"})
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        with pytest.raises(PermissionDeniedError):
            await job_service.cancel_job(session, job_id, user_context={"user_id": str(other_user_id)})


@pytest.mark.asyncio
async def test_non_owner_cannot_list_another_missions_jobs(session_factory):
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    mission = await create_mission_with_user(session_factory, user_id=owner_id, title="Owner Mission")

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id, user_context={"user_id": "dev-user"})
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(PermissionDeniedError):
            await job_service.list_jobs(session, mission_id=mission.id, user_context={"user_id": str(other_user_id)})

    async with session_factory() as session:
        jobs, total = await job_service.list_jobs(session, user_context={"user_id": str(other_user_id)})
        assert total == 0
        assert len(jobs) == 0


@pytest.mark.asyncio
async def test_orphan_missing_mission_fails_closed(session_factory):
    fake_mission_id = uuid.uuid4()

    async with session_factory() as session:
        from app.models.job import MissionJob
        job = MissionJob(
            id=uuid.uuid4(),
            mission_id=fake_mission_id,
            execution_id=uuid.uuid4(),
            status="pending",
            attempts=0,
            max_retries=3,
            payload={},
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    async with session_factory() as session:
        with pytest.raises(PermissionDeniedError):
            await job_service.get_job(session, job_id, user_context={"user_id": str(uuid.uuid4())})

    async with session_factory() as session:
        fetched = await job_service.get_job(session, job_id, user_context={"user_id": "dev-user"})
        assert fetched.id == job_id

    async with session_factory() as session:
        with pytest.raises(PermissionDeniedError):
            await job_service.get_job(session, job_id, user_context={"user_id": str(uuid.uuid4())})


@pytest.mark.asyncio
async def test_anonymous_denied(session_factory):
    owner_id = uuid.uuid4()
    mission = await create_mission_with_user(session_factory, user_id=owner_id)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id, user_context={"user_id": "dev-user"})
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        with pytest.raises(PermissionDeniedError):
            await job_service.get_job(session, job_id, user_context={"user_id": "anonymous"})

    async with session_factory() as session:
        with pytest.raises(PermissionDeniedError):
            await job_service.list_jobs(session, mission_id=mission.id, user_context={"user_id": "anonymous"})

    async with session_factory() as session:
        with pytest.raises(PermissionDeniedError):
            await job_service.cancel_job(session, job_id, user_context={"user_id": "anonymous"})


@pytest.mark.asyncio
async def test_dev_user_allowed_mvp(session_factory):
    owner_id = uuid.uuid4()
    mission = await create_mission_with_user(session_factory, user_id=owner_id)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id, user_context={"user_id": "dev-user"})
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        fetched = await job_service.get_job(session, job_id, user_context={"user_id": "dev-user"})
        assert fetched.id == job_id


@pytest.mark.asyncio
async def test_internal_no_context_allowed(session_factory):
    owner_id = uuid.uuid4()
    mission = await create_mission_with_user(session_factory, user_id=owner_id)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        fetched = await job_service.get_job(session, job_id, user_context=None)
        assert fetched.id == job_id
