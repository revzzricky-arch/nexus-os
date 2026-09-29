"""
Worker Tests - Phase 3 PR 3.1 with heartbeat isolation fix
- pending execution success failure retry heartbeat cancellation expired lease recovery
- New: heartbeat independent session, long-running does NOT become stale, ownership mismatch rejection
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
    try:
        await engine.dispose()
    except Exception:
        pass


async def create_mission(factory, title="Worker Test Mission", status="draft", user_id=None):
    async with factory() as session:
        m = Mission(
            id=uuid.uuid4(),
            user_id=user_id,
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

    with patch("app.services.orchestrator.orchestrator_service.execute_mission_isolated", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = {"mission_id": str(mission.id), "status": "completed"}

        worker = MissionWorker(worker_id="test-worker-1", poll_interval=0.1, session_factory=session_factory)

        async with session_factory() as session:
            claimed = await job_service.claim_job(session, worker_id=worker.worker_id)
            await session.commit()
            assert claimed is not None

            result = await worker.execute_job(session, claimed.id)
            await session.commit()

            assert result is True

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

    with patch("app.services.orchestrator.orchestrator_service.execute_mission_isolated", new_callable=AsyncMock) as mock_start:
        mock_start.side_effect = Exception("orchestrator failed")

        worker = MissionWorker(worker_id="test-worker-fail", poll_interval=0.1, session_factory=session_factory)

        async with session_factory() as session:
            claimed = await job_service.claim_job(session, worker_id=worker.worker_id)
            await session.commit()

            result = await worker.execute_job(session, claimed.id)
            await session.commit()

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

    with patch("app.services.orchestrator.orchestrator_service.execute_mission_isolated", new_callable=AsyncMock) as mock_start:
        mock_start.side_effect = Exception("always fail")

        worker = MissionWorker(worker_id="test-worker-retry", session_factory=session_factory)

        async with session_factory() as session:
            claimed = await job_service.claim_job(session, worker_id=worker.worker_id)
            await session.commit()
            await worker.execute_job(session, claimed.id)
            await session.commit()

        async with session_factory() as session:
            claimed2 = await job_service.claim_job(session, worker_id=worker.worker_id)
            if claimed2:
                await session.commit()
                await worker.execute_job(session, claimed2.id)
                await session.commit()

        async with session_factory() as session:
            job = await job_service.get_job(session, job_id)
            assert job.status in ["pending", "failed"]
            if job.status == "pending":
                claimed3 = await job_service.claim_job(session, worker_id=worker.worker_id)
                await session.commit()
                if claimed3:
                    await worker.execute_job(session, claimed3.id)
                    await session.commit()
                    job = await job_service.get_job(session, job_id)
                    assert job.status == "failed"


@pytest.mark.asyncio
async def test_worker_heartbeat_independent_session(session_factory):
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    with patch("app.services.orchestrator.orchestrator_service.execute_mission_isolated", new_callable=AsyncMock) as mock_start:
        async def long_task(*args, **kwargs):
            await asyncio.sleep(0.35)
            return {"status": "completed"}

        mock_start.side_effect = long_task

        worker = MissionWorker(worker_id="test-worker-hb", poll_interval=0.1, heartbeat_interval=0.05, session_factory=session_factory)

        async with session_factory() as session:
            claimed = await job_service.claim_job(session, worker_id=worker.worker_id)
            await session.commit()

            await worker.execute_job(session, claimed.id)
            await session.commit()

        async with session_factory() as session:
            job = await job_service.get_job(session, job_id)
            assert job.status == "completed"


@pytest.mark.asyncio
async def test_worker_long_running_not_stale(session_factory):
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        claimed = await job_service.claim_job(session, worker_id="test-worker-long", lease_timeout=1)
        await session.commit()
        assert claimed is not None

    async def heartbeat_simulation():
        for _ in range(6):
            await asyncio.sleep(0.1)
            async with session_factory() as hb_sess:
                await job_service.heartbeat_job(hb_sess, job_id, "test-worker-long")
                await hb_sess.commit()

    hb_task = asyncio.create_task(heartbeat_simulation())

    await asyncio.sleep(0.35)
    async with session_factory() as check_session:
        recovered = await job_service.recover_stale_jobs(check_session, lease_timeout=1)
        await check_session.commit()
        assert len(recovered) == 0, "Healthy long-running worker with independent heartbeat commits should NOT be reclaimed"

    await hb_task

    await asyncio.sleep(1.2)
    async with session_factory() as check_session:
        recovered2 = await job_service.recover_stale_jobs(check_session, lease_timeout=1)
        await check_session.commit()
        assert len(recovered2) == 1
        assert "test-worker-long" in recovered2[0].error


@pytest.mark.asyncio
async def test_worker_heartbeat_committed_independently(session_factory):
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        claimed = await job_service.claim_job(session, worker_id="worker-hb-commit")
        await session.commit()
        initial_hb = claimed.heartbeat_at

    await asyncio.sleep(0.05)
    async with session_factory() as hb_session:
        hb_job = await job_service.heartbeat_job(hb_session, job_id, "worker-hb-commit")
        await hb_session.commit()
        assert hb_job.heartbeat_at > initial_hb

    async with session_factory() as session:
        job = await job_service.get_job(session, job_id)
        assert job.heartbeat_at > initial_hb


@pytest.mark.asyncio
async def test_worker_ownership_mismatch_heartbeat_rejection(session_factory):
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        claimed = await job_service.claim_job(session, worker_id="owner-worker")
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(Exception):
            await job_service.heartbeat_job(session, job_id, "other-worker")


@pytest.mark.asyncio
async def test_worker_cancellation(session_factory):
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        claimed = await job_service.claim_job(session, worker_id="worker-cancel-test")
        await session.commit()
        assert claimed.status == "running"

    async with session_factory() as session:
        cancelled = await job_service.cancel_job(session, job_id)
        await session.commit()
        assert cancelled.status == "cancelled"

    with patch("app.services.orchestrator.orchestrator_service.execute_mission_isolated", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = {"status": "completed"}

        worker = MissionWorker(worker_id="worker-cancel-test", session_factory=session_factory)

        async with session_factory() as session:
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

    async with session_factory() as session:
        job = await session.get(MissionJob, j1_id)
        job.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=LEASE_TIMEOUT_SECONDS + 10)
        job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=LEASE_TIMEOUT_SECONDS + 10)
        await session.commit()

    async with session_factory() as session:
        job = await session.get(MissionJob, j2_id)
        job.heartbeat_at = datetime.now(timezone.utc)
        job.locked_at = datetime.now(timezone.utc)
        await session.commit()

    async with session_factory() as session:
        recovered = await job_service.recover_stale_jobs(session, lease_timeout=LEASE_TIMEOUT_SECONDS)
        await session.commit()

        assert len(recovered) == 1
        assert recovered[0].id == j1_id
        assert "old-worker-1" in recovered[0].error

        new_worker = MissionWorker(worker_id="new-worker", session_factory=session_factory)
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

    with patch("app.services.orchestrator.orchestrator_service.execute_mission_isolated", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = {"status": "completed"}

        worker = MissionWorker(worker_id="test-worker-once", session_factory=session_factory)

        async with session_factory() as session:
            job_id = await worker.run_once(session)
            await session.commit()
            assert job_id is not None

        async with session_factory() as session:
            job_id2 = await worker.run_once(session)
            await session.commit()
            assert job_id2 is None


@pytest.mark.asyncio
async def test_worker_uses_isolated_entry_point(session_factory):
    """Worker must invoke execute_mission_isolated, not legacy start_mission"""
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    with patch("app.services.orchestrator.orchestrator_service.execute_mission_isolated", new_callable=AsyncMock) as mock_isolated, \
         patch("app.services.orchestrator.orchestrator_service.start_mission", new_callable=AsyncMock) as mock_legacy:

        mock_isolated.return_value = {"mission_id": str(mission.id), "status": "completed"}
        mock_legacy.return_value = {"mission_id": str(mission.id), "status": "completed"}

        worker = MissionWorker(worker_id="test-worker-isolated", session_factory=session_factory)

        async with session_factory() as session:
            claimed = await job_service.claim_job(session, worker_id=worker.worker_id)
            await session.commit()

            result = await worker.execute_job(session, claimed.id)
            await session.commit()

            assert result is True
            mock_isolated.assert_called_once()
            mock_legacy.assert_not_called(), "Worker must NOT invoke legacy start_mission, must use execute_mission_isolated"


@pytest.mark.asyncio
async def test_paused_job_not_auto_requeued(session_factory):
    """Regression: deliberately paused job must not be auto-requeued by stale recovery"""
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()

        claimed = await job_service.claim_job(session, worker_id="worker-pause-test")
        await session.commit()
        job_id = claimed.id

        # Simulate intentional pause
        paused = await job_service.update_job_status(session, job_id, "paused")
        await session.commit()
        assert paused.status == "paused"

        # Make heartbeat old - should NOT be requeued because paused is intentional
        job = await session.get(MissionJob, job_id)
        job.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=LEASE_TIMEOUT_SECONDS + 100)
        job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=LEASE_TIMEOUT_SECONDS + 100)
        # Keep locked_by to simulate paused with old heartbeat
        await session.commit()

    async with session_factory() as session:
        recovered = await job_service.recover_stale_jobs(session, lease_timeout=LEASE_TIMEOUT_SECONDS)
        await session.commit()
        # Paused should remain paused
        assert len(recovered) == 0, "Paused job must NOT be auto-requeued"

        fresh = await job_service.get_job(session, job_id)
        assert fresh.status == "paused", "Paused job must remain paused"


@pytest.mark.asyncio
async def test_awaiting_approval_not_treated_as_crashed(session_factory):
    """awaiting_approval must NOT be treated as crashed running job (deferred to PR 3.2/3.6)"""
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()

        claimed = await job_service.claim_job(session, worker_id="worker-approval-test")
        await session.commit()
        job_id = claimed.id

        # Move to awaiting_approval
        awaiting = await job_service.update_job_status(session, job_id, "awaiting_approval")
        await session.commit()
        assert awaiting.status == "awaiting_approval"

        # Make heartbeat old
        job = await session.get(MissionJob, job_id)
        job.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=LEASE_TIMEOUT_SECONDS + 100)
        job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=LEASE_TIMEOUT_SECONDS + 100)
        await session.commit()

    async with session_factory() as session:
        recovered = await job_service.recover_stale_jobs(session, lease_timeout=LEASE_TIMEOUT_SECONDS)
        await session.commit()
        assert len(recovered) == 0, "awaiting_approval must NOT be reclaimed in PR 3.1"

        fresh = await job_service.get_job(session, job_id)
        assert fresh.status == "awaiting_approval"


@pytest.mark.asyncio
async def test_recovery_preserves_locked_by(session_factory):
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()

        claimed = await job_service.claim_job(session, worker_id="preserved-worker-123")
        await session.commit()
        job_id = claimed.id

    async with session_factory() as session:
        job = await session.get(MissionJob, job_id)
        job.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=LEASE_TIMEOUT_SECONDS + 10)
        job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=LEASE_TIMEOUT_SECONDS + 10)
        await session.commit()

    async with session_factory() as session:
        recovered = await job_service.recover_stale_jobs(session, lease_timeout=LEASE_TIMEOUT_SECONDS)
        await session.commit()
        assert len(recovered) == 1
        assert "preserved-worker-123" in recovered[0].error


@pytest.mark.asyncio
async def test_run_once_commits_claim_before_execution(session_factory):
    """Regression: run_once must COMMIT claim transaction immediately before execute_job, releasing FOR UPDATE lock"""
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    # Instrument ordering: track commit and execute_job calls
    call_order = []

    original_commit = None

    with patch("app.services.orchestrator.orchestrator_service.execute_mission_isolated", new_callable=AsyncMock) as mock_exec:
        async def exec_side_effect(*args, **kwargs):
            call_order.append("execute_job")
            await asyncio.sleep(0.1)
            return {"status": "completed"}

        mock_exec.side_effect = exec_side_effect

        worker = MissionWorker(worker_id="test-commit-order", session_factory=session_factory)

        # Patch the session.commit inside run_once to track ordering
        # We wrap the session_factory to intercept commit
        async with session_factory() as session:
            # Instrument session.commit
            orig_commit = session.commit

            async def tracked_commit():
                call_order.append("commit_claim")
                await orig_commit()

            session.commit = tracked_commit

            # Need to also track execute_job separately - we already track via mock_exec
            # But run_once will commit claim via session.commit, then execute via separate session
            # For this test, we will directly test run_once ordering by checking that commit happens before execute

            # Use a custom worker that records commit before execute
            # Simpler: test the logic of run_once by mocking claim_job to return job and checking commit called before execute_job

            # Restore and do more direct test below
            session.commit = orig_commit

        # More direct ordering test: mock claim_job and check commit called before execute_job
        with patch.object(job_service, "claim_job", new_callable=AsyncMock) as mock_claim:
            async def claim_side_effect(*args, **kwargs):
                # Return a job-like object
                async with session_factory() as s:
                    j = await s.get(MissionJob, job_id)
                    return j

            mock_claim.side_effect = claim_side_effect

            # Create a tracking session
            async with session_factory() as tracking_session:
                commit_called = False
                execute_called = False
                order = []

                orig_commit2 = tracking_session.commit

                async def tracked_commit2():
                    nonlocal commit_called
                    commit_called = True
                    order.append("commit")
                    await orig_commit2()

                tracking_session.commit = tracked_commit2

                # Patch execute_job to track
                orig_execute = worker.execute_job

                async def tracked_execute(sess, jid):
                    nonlocal execute_called
                    order.append("execute")
                    execute_called = True
                    # Verify commit happened before execute
                    assert "commit" in order, "Claim transaction must be committed before execution begins"
                    assert order.index("commit") < order.index("execute"), "Commit must occur before execute_job"
                    return True

                worker.execute_job = tracked_execute

                # Mock claim_job to return job without needing DB
                async with session_factory() as s:
                    job_obj = await s.get(MissionJob, job_id)

                # Simulate run_once logic manually to verify ordering
                # Actually call run_once which should commit before execute
                # We need to make claim_job return our job
                with patch.object(job_service, "claim_job", new_callable=AsyncMock) as mock_claim2:
                    mock_claim2.return_value = job_obj

                    # Reset order
                    order.clear()
                    # Need to re-patch commit for this session
                    tracking_session.commit = tracked_commit2
                    worker.execute_job = tracked_execute

                    result = await worker.run_once(tracking_session)
                    # After run_once, order should have commit before execute
                    assert "commit" in order
                    assert "execute" in order
                    assert order.index("commit") < order.index("execute")

                worker.execute_job = orig_execute


@pytest.mark.asyncio
async def test_heartbeat_cancellation_during_execution(session_factory):
    """Verify heartbeat/cancellation can use another session while execution is in progress"""
    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()
        job_id = job.id

    with patch("app.services.orchestrator.orchestrator_service.execute_mission_isolated", new_callable=AsyncMock) as mock_exec:
        async def long_exec(*args, **kwargs):
            # During execution, try heartbeat and cancellation from independent sessions
            await asyncio.sleep(0.2)

            # Heartbeat from independent session should succeed while execution in progress
            async with session_factory() as hb_sess:
                hb = await job_service.heartbeat_job(hb_sess, job_id, "test-hb-cancel")
                await hb_sess.commit()
                assert hb.heartbeat_at is not None

            # Cancellation from independent session should also be possible (will be observed)
            # We don't actually cancel here, just prove independent transaction works

            return {"status": "completed"}

        mock_exec.side_effect = long_exec

        worker = MissionWorker(worker_id="test-hb-cancel", heartbeat_interval=0.05, session_factory=session_factory)

        async with session_factory() as session:
            claimed = await job_service.claim_job(session, worker_id=worker.worker_id)
            await session.commit()
            assert claimed.id == job_id

        async with session_factory() as exec_session:
            result = await worker.execute_job(exec_session, job_id)
            await exec_session.commit()
            assert result is True


@pytest.mark.asyncio
async def test_claim_job_postgres_error_not_silently_fallback(session_factory):
    """Regression: PostgreSQL claim error must NOT be silently converted into unlocked claim"""
    # This test verifies the dialect logic
    # For SQLite, fallback is allowed
    # For PostgreSQL (or empty dialect which defaults to postgres path), errors must propagate

    mission = await create_mission(session_factory)

    async with session_factory() as session:
        job = await job_service.create_job(session, mission_id=mission.id)
        await session.commit()

    # For SQLite session, claim should work via fallback
    async with session_factory() as session:
        claimed = await job_service.claim_job(session, worker_id="test-sqlite")
        await session.commit()
        assert claimed is not None

    # Now test that for a session with postgres dialect, error propagates
    # We mock session.get_bind to return postgres dialect and make SELECT ... FOR UPDATE SKIP LOCKED fail
    from unittest.mock import MagicMock

    # Create a mock session that simulates postgres dialect and failing query
    class MockPostgresDialect:
        name = "postgresql"

    class MockBind:
        dialect = MockPostgresDialect()

    class MockSession:
        def get_bind(self):
            return MockBind()

        async def execute(self, query):
            # Simulate DB error for SKIP LOCKED query
            raise Exception("Simulated PostgreSQL error - should propagate, not fallback")

    mock_session = MockSession()

    # Should raise, not fallback to unlocked claim
    with pytest.raises(Exception) as exc_info:
        await job_service.claim_job(mock_session, worker_id="test-postgres-error")

    assert "Simulated PostgreSQL error" in str(exc_info.value)

    # Unknown dialect should fail closed
    class MockUnknownDialect:
        name = "oracle"

    class MockUnknownBind:
        dialect = MockUnknownDialect()

    class MockUnknownSession:
        def get_bind(self):
            return MockUnknownBind()

        async def execute(self, query):
            return None

    mock_unknown = MockUnknownSession()

    with pytest.raises(Exception) as exc_info2:
        await job_service.claim_job(mock_unknown, worker_id="test-unknown")

    assert "Unsupported dialect" in str(exc_info2.value)
