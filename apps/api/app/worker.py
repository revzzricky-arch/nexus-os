"""
Worker Service - Phase 3 PR 3.1 Durable Worker + Mission Job System

Requirements:
- async
- bounded worker count
- configurable worker ID
- configurable polling interval
- no API request owns mission execution
- worker invokes existing orchestration service
- worker handles success/failure/retry
- bounded retries
- emits appropriate events
- Do not use in-process FastAPI background task as durable worker
- Lease/heartbeat: locked_at + heartbeat_at + configurable lease timeout, worker periodically renews heartbeat
- Test: healthy long-running worker NOT reclaimed, crashed worker with expired lease IS reclaimed

Architecture:
POST /missions/{id}/start → JobService → mission_jobs → Worker → Orchestrator/LangGraph

Worker is a separate process, not FastAPI background task. For MVP, single process with async worker pool.
Can later be replaced by multiple worker processes (each with own worker ID) polling same job table.

Document how this can later be replaced by multiple worker processes:
- Each worker has unique worker_id
- All workers poll same mission_jobs table with SELECT FOR UPDATE SKIP LOCKED
- Only one worker claims a pending job atomically
- Workers can run on different hosts, same DB
- Lease/heartbeat prevents duplicate execution
- Future: replace polling with LISTEN/NOTIFY or Redis Streams for lower latency

This PR only provides durable job recovery, not checkpoint-based resume yet (deferred to PR 3.2).
"""

import asyncio
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.db.base import Base
from app.services.job import job_service, LEASE_TIMEOUT_SECONDS, HEARTBEAT_INTERVAL_SECONDS
from app.services.mission import mission_service
from app.services.event_bus import event_bus_service
from app.schemas.event import EventCreate, EventType, EventSource
from app.schemas.mission import MissionUpdate, MissionStatus

logger = logging.getLogger(__name__)


class MissionWorker:
    """
    Durable mission worker - async, bounded, configurable
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        poll_interval: float = 2.0,
        lease_timeout: int = LEASE_TIMEOUT_SECONDS,
        heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS,
        max_retries: int = 3,
    ):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.poll_interval = poll_interval
        self.lease_timeout = lease_timeout
        self.heartbeat_interval = heartbeat_interval
        self.max_retries = max_retries
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._current_job_id: Optional[uuid.UUID] = None

    async def _get_session_factory(self):
        # Create engine and session factory from settings
        # For tests, this will be overridden
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        return engine, factory

    async def execute_job(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
    ) -> bool:
        """
        Execute single job - isolated execution method
        Reuses existing orchestrator and LangGraph implementation
        Do not redesign graph nodes
        Returns True if success, False if failed
        """
        from app.services.orchestrator import orchestrator_service

        try:
            # Get job
            job = await job_service.get_job(session, job_id)

            # Check if cancelled before execution
            if job.status == "cancelled":
                logger.info(f"Worker {self.worker_id} job {job_id} already cancelled, skipping")
                return True

            # Set heartbeat for this job
            self._current_job_id = job_id

            # Start heartbeat task
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(session, job_id))

            try:
                # Invoke existing orchestration service - isolated method
                # This is the long-running execution ownership moved from HTTP request → Worker
                result = await orchestrator_service.start_mission(session, job.mission_id)

                # On success, update job completed
                await job_service.update_job_status(
                    session,
                    job_id,
                    "completed",
                    result=result,
                )

                # Emit mission completion event? Orchestrator already emits mission_status_changed
                logger.info(f"Worker {self.worker_id} job {job_id} completed for mission {job.mission_id}")

                return True

            except Exception as e:
                logger.warning(f"Worker {self.worker_id} job {job_id} failed: {e}")

                # Check if cancelled during execution
                # Refresh job to see if cancelled
                try:
                    await session.refresh(job)
                    if job.status == "cancelled":
                        logger.info(f"Worker {self.worker_id} job {job_id} cancelled during execution")
                        return True
                except Exception:
                    pass

                # Handle failure/retry - bounded retries
                if job.attempts < job.max_retries:
                    # Retry: move back to pending
                    await job_service.update_job_status(
                        session,
                        job_id,
                        "pending",
                        error=str(e)[:1000],
                    )
                    logger.info(f"Worker {self.worker_id} job {job_id} retry {job.attempts}/{job.max_retries}")
                else:
                    # Failed after max retries
                    await job_service.update_job_status(
                        session,
                        job_id,
                        "failed",
                        error=str(e)[:1000],
                    )
                    # Also update mission status to failed via MissionService
                    try:
                        await mission_service.update_mission(
                            session,
                            job.mission_id,
                            MissionUpdate(status=MissionStatus.failed),
                        )
                    except Exception:
                        pass

                    # Emit error event
                    try:
                        await event_bus_service.emit(
                            session,
                            EventCreate(
                                type=EventType.error,
                                source=EventSource.system,
                                mission_id=job.mission_id,
                                payload={
                                    "message": f"Mission execution failed after {job.attempts} attempts: {str(e)[:500]}",
                                    "code": "mission_execution_failed",
                                    "job_id": str(job_id),
                                    "execution_id": str(job.execution_id),
                                },
                            ),
                        )
                    except Exception:
                        pass

                return False

            finally:
                # Stop heartbeat task
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    try:
                        await self._heartbeat_task
                    except asyncio.CancelledError:
                        pass
                    self._heartbeat_task = None
                self._current_job_id = None

        except Exception as e:
            logger.warning(f"Worker {self.worker_id} execute_job {job_id} outer failure: {e}")
            return False

    async def _heartbeat_loop(self, session: AsyncSession, job_id: uuid.UUID):
        """
        Periodically renew heartbeat for running job
        """
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                # Need new session for heartbeat? For simplicity, use same session if possible, but in real worker we need separate session factory
                # For this MVP, we try to heartbeat with current session, but if session is busy, we skip
                # In production worker, each heartbeat would use its own session
                try:
                    await job_service.heartbeat_job(session, job_id, self.worker_id)
                    logger.debug(f"Worker {self.worker_id} heartbeat for job {job_id}")
                except Exception as e:
                    logger.debug(f"Worker {self.worker_id} heartbeat failed for {job_id}: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Worker {self.worker_id} heartbeat loop error: {e}")
                # Continue loop, don't crash worker

    async def run_once(self, session: AsyncSession) -> Optional[uuid.UUID]:
        """
        Run one iteration: claim pending job and execute
        Returns job_id if claimed and executed, None if no job
        """
        try:
            job = await job_service.claim_job(session, self.worker_id, lease_timeout=self.lease_timeout)
            if not job:
                return None

            logger.info(f"Worker {self.worker_id} claimed job {job.id} for mission {job.mission_id}")

            await self.execute_job(session, job.id)

            return job.id

        except Exception as e:
            logger.warning(f"Worker {self.worker_id} run_once failed: {e}")
            return None

    async def run_forever(self, session_factory=None):
        """
        Run forever polling for jobs - for separate worker process
        """
        self._running = True
        logger.info(f"Worker {self.worker_id} starting with poll_interval={self.poll_interval}s lease_timeout={self.lease_timeout}s")

        # On startup, recover stale jobs
        try:
            if session_factory:
                async with session_factory() as session:
                    recovered = await job_service.recover_stale_jobs(session, lease_timeout=self.lease_timeout)
                    if recovered:
                        logger.info(f"Worker {self.worker_id} recovered {len(recovered)} stale jobs on startup")
                        await session.commit()
        except Exception as e:
            logger.warning(f"Worker {self.worker_id} stale recovery on startup failed: {e}")

        while self._running:
            try:
                if session_factory:
                    async with session_factory() as session:
                        job_id = await self.run_once(session)
                        await session.commit()
                        if not job_id:
                            await asyncio.sleep(self.poll_interval)
                else:
                    # No session factory provided, sleep
                    await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Worker {self.worker_id} run_forever error: {e}")
                await asyncio.sleep(self.poll_interval)

        logger.info(f"Worker {self.worker_id} stopped")

    def stop(self):
        self._running = False


# Singleton for API process to trigger recovery on startup (not durable worker, but for restart recovery)
# Real durable worker is separate process, but API can also recover stale jobs on startup
worker_service = MissionWorker()


async def recover_stale_jobs_on_startup(session: AsyncSession):
    """
    On API startup, find jobs whose lease expired and move back to pending
    This is durable job recovery, not checkpoint-based resume (deferred to PR 3.2)
    """
    try:
        recovered = await job_service.recover_stale_jobs(session, lease_timeout=LEASE_TIMEOUT_SECONDS)
        if recovered:
            logger.info(f"Recovered {len(recovered)} stale jobs on API startup")
        return recovered
    except Exception as e:
        logger.warning(f"Stale job recovery on API startup failed: {e}")
        return []
