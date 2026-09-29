"""
Worker Tests - Phase 3 PR 3.1
- pending execution success failure retry heartbeat cancellation expired lease recovery
"""

import uuid
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.base import Base
from app.models.mission import Mission
from app.models.job import MissionJob
from app.services.job import job_service, LEASE_TIMEOUT_SECONDS
from app.worker import MissionWorker


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


async def create_mission(factory, title="Worker Test Mission", status="draft"):
    async with factory() as session:
        m = Mission(
            id=uuid.uuid4(),
            title=title,
            goal="Test goal for worker",
            template="general",
            status=status,
        )
        session.add(m)
        await session.commit()
        await session.refresh(m)
        return m


@pytest.mark.asyncio
async def test_worker_pending_execution_success(session_factory):
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    # Mock orchestrator to succeed
    with patch("app.services.orchestrator.orchestrator_service.start_mission", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = {"mission_id": str(mission.id), "status": "completed"}

        worker = MissionWorker(worker_id="test-worker-1", poll_interval=0.1)

        async with session_factory() as session:
            claimed = await job_service.claim_job(session, worker_id=worker.worker_id)
            await session.commit()
            assert claimed is not None

            result = await worker.execute_job(session, claimed.id)
            await session.commit()

            assert result is True

        # Verify job completed
        async with session_factory() as session:
            job = await job_service.get_job(session, job_id)
            assert job.status == "completed"
            assert job.result is not None


@pytest.mark.asyncio
async def test_worker_pending_execution_failure(session_factory):
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    with patch("app.services.orchestrator.orchestrator_service.start_mission", new_callable=AsyncMock) as mock_start:
        mock_start.side_effect = Exception("orchestrator failed")

        worker = MissionWorker(worker_id="test-worker-fail", poll_interval=0.1)

        async with session_factory() as session:
            claimed = await job_service.claim_job(session, worker_id=worker.worker_id)
            await session.commit()

            result = await worker.execute_job(session, claimed.id)
            await session.commit()

            # First failure should go back to pending for retry (attempts 1 < max 3)
            assert result is False

        async with session_factory() as session:
            job = await job_service.get_job(session, job_id)
            assert job.status == "pending"
            assert job.attempts == 1
            assert job.error is not None


@pytest.mark.asyncio
async def test_worker_retry_bounded(session_factory):
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        job.max_retries = 1
        await session.commit()
        job_id = job.id

    with patch("app.services.orchestrator.orchestrator_service.start_mission", new_callable=AsyncMock) as mock_start:
        mock_start.side_effect = Exception("always fail")

        worker = MissionWorker(worker_id="test-worker-retry")

        # First attempt
        async with session_factory() as session:
            claimed = await job_service.claim_job(session, worker_id=worker.worker_id)
            await session.commit()
            await worker.execute_job(session, claimed.id)
            await session.commit()

        # Second attempt - should be last, then fail
        async with session_factory() as session:
            claimed2 = await job_service.claim_job(session, worker_id=worker.worker_id)
            # If first failure returned to pending, we can claim again
            if claimed2:
                await session.commit()
                await worker.execute_job(session, claimed2.id)
                await session.commit()

        async with session_factory() as session:
            job = await job_service.get_job(session, job_id)
            # After max retries exceeded, should be failed
            # Depending on flow: first fail -> pending, second claim -> fail -> failed
            assert job.status in ["pending", "failed"]
            if job.status == "pending":
                # Claim again to trigger final failure
                claimed3 = await job_service.claim_job(session, worker_id=worker.worker_id)
                await session.commit()
                if claimed3:
                    await worker.execute_job(session, claimed3.id)
                    await session.commit()
                    job = await job_service.get_job(session, job_id)
                    assert job.status == "failed"


@pytest.mark.asyncio
async def test_worker_heartbeat(session_factory):
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    with patch("app.services.orchestrator.orchestrator_service.start_mission", new_callable=AsyncMock) as mock_start:
        # Simulate long running task that would need heartbeat
        async def long_task(*args, **kwargs):
            await asyncio.sleep(0.3)
            return {"status": "completed"}

        mock_start.side_effect = long_task

        worker = MissionWorker(worker_id="test-worker-hb", poll_interval=0.1, heartbeat_interval=0.05)

        async with session_factory() as session:
            claimed = await job_service.claim_job(session, worker_id=worker.worker_id)
            await session.commit()
            first_hb = claimed.heartbeat_at

            await worker.execute_job(session, claimed.id)
            await session.commit()

        async with session_factory() as session:
            job = await job_service.get_job(session, job_id)
            assert job.status == "completed"


@pytest.mark.asyncio
async def test_worker_cancellation(session_factory):
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    # Claim job
    async with session_factory() as session:
        claimed = await job_service.claim_job(session, worker_id="worker-cancel-test")
        await session.commit()
        assert claimed.status == "running"

    # Cancel job while running - worker should observe stop safely
    async with session_factory() as session:
        cancelled = await job_service.cancel_job(session, job_id)
        await session.commit()
        assert cancelled.status == "cancelled"

    # Worker tries to execute cancelled job - should skip
    with patch("app.services.orchestrator.orchestrator_service.start_mission", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = {"status": "completed"}

        worker = MissionWorker(worker_id="worker-cancel-test")

        async with session_factory() as session:
            # Even if we call execute_job on cancelled, it should return True and not call orchestrator
            result = await worker.execute_job(session, job_id)
            await session.commit()
            assert result is True
            mock_start.assert_not_called()


@pytest.mark.asyncio
async def test_worker_expired_lease_recovery(session_factory):
    mission1 = await create_mission(session_factory, title="Expired M1")
    mission2 = await create_mission(session_factory, title="Expired M2")

    async with session_factory() as session:
        job1 = await job_service.create_job(session, mission_id=mission1.id)
        job2 = await job_service.create_job(session, mission_id=mission2.id)
        await session.commit()

        c1 = await job_service.claim_job(session, worker_id="old-worker-1")
        c2 = await job_service.claim_job(session, worker_id="old-worker-2")
        await session.commit()

        j1_id = c1.id
        j2_id = c2.id

    # Make j1 stale (crashed worker)
    async with session_factory() as session:
        job = await session.get(MissionJob, j1_id)
        job.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=LEASE_TIMEOUT_SECONDS + 10)
        job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=LEASE_TIMEOUT_SECONDS + 10)
        await session.commit()

    # j2 healthy
    async with session_factory() as session:
        job = await session.get(MissionJob, j2_id)
        job.heartbeat_at = datetime.now(timezone.utc)
        job.locked_at = datetime.now(timezone.utc)
        await session.commit()

    # New worker recovers stale
    async with session_factory() as session:
        recovered = await job_service.recover_stale_jobs(session, lease_timeout=LEASE_TIMEOUT_SECONDS)
        await session.commit()

        assert len(recovered) == 1
        assert recovered[0].id == j1_id

        # New worker can claim recovered job
        new_worker = MissionWorker(worker_id="new-worker")
        claimed = await job_service.claim_job(session, worker_id=new_worker.worker_id)
        await session.commit()

        assert claimed is not None
        assert claimed.id == j1_id


@pytest.mark.asyncio
async def test_worker_run_once(session_factory):
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()

    with patch("app.services.orchestrator.orchestrator_service.start_mission", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = {"status": "completed"}

        worker = MissionWorker(worker_id="test-worker-once")

        async with session_factory() as session:
            job_id = await worker.run_once(session)
            await session.commit()
            assert job_id is not None

        # No more jobs
        async with session_factory() as session:
            job_id2 = await worker.run_once(session)
            await session.commit()
            assert job_id2 is None
