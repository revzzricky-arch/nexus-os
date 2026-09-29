"""
Worker Service - Phase 3 PR 3.1 Durable Worker + Mission Job System
Fixes per PR #8 review:
- Heartbeat uses independent AsyncSession / transaction, not shared execution session
- Heartbeat transaction: BEGIN verify job_id + locked_by + valid status update heartbeat_at COMMIT
- Execution session remains independent
- If heartbeat fails because ownership lost/cancelled, surface to worker and stop unsafe continuation
"""

import asyncio
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable

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
    def __init__(
        self,
        worker_id: Optional[str] = None,
        poll_interval: float = 2.0,
        lease_timeout: int = LEASE_TIMEOUT_SECONDS,
        heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS,
        max_retries: int = 3,
        session_factory: Optional[Callable[[], Awaitable[AsyncSession]]] = None,
    ):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.poll_interval = poll_interval
        self.lease_timeout = lease_timeout
        self.heartbeat_interval = heartbeat_interval
        self.max_retries = max_retries
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._current_job_id: Optional[uuid.UUID] = None
        self._session_factory = session_factory
        self._heartbeat_failed = False
        self._heartbeat_failure_reason: Optional[str] = None

    def set_session_factory(self, factory):
        self._session_factory = factory

    async def _get_session_factory(self):
        if self._session_factory:
            return None, self._session_factory
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        return engine, factory

    async def execute_job(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
    ) -> bool:
        from app.services.orchestrator import orchestrator_service

        try:
            job = await job_service.get_job(session, job_id)

            if job.status == "cancelled":
                logger.info(f"Worker {self.worker_id} job {job_id} already cancelled, skipping")
                return True

            self._current_job_id = job_id
            self._heartbeat_failed = False
            self._heartbeat_failure_reason = None

            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(job_id))

            try:
                result = await orchestrator_service.start_mission(session, job.mission_id)

                if self._heartbeat_failed:
                    logger.warning(
                        f"Worker {self.worker_id} job {job_id} heartbeat failed during execution: {self._heartbeat_failure_reason} - stopping unsafe continuation"
                    )
                    try:
                        if self._session_factory:
                            async with self._session_factory() as check_session:
                                fresh_job = await job_service.get_job(check_session, job_id)
                                if fresh_job.status == "cancelled":
                                    logger.info(f"Worker {self.worker_id} job {job_id} cancelled during execution, aborting")
                                    return True
                    except Exception:
                        pass
                    return False

                await job_service.update_job_status(
                    session,
                    job_id,
                    "completed",
                    result=result,
                )

                logger.info(f"Worker {self.worker_id} job {job_id} completed for mission {job.mission_id}")
                return True

            except Exception as e:
                logger.warning(f"Worker {self.worker_id} job {job_id} failed: {e}")

                if self._heartbeat_failed:
                    try:
                        if self._session_factory:
                            async with self._session_factory() as check_session:
                                fresh_job = await job_service.get_job(check_session, job_id)
                                if fresh_job.status == "cancelled":
                                    logger.info(f"Worker {self.worker_id} job {job_id} cancelled during execution")
                                    return True
                    except Exception:
                        pass

                try:
                    await session.refresh(job)
                    if job.status == "cancelled":
                        logger.info(f"Worker {self.worker_id} job {job_id} cancelled during execution")
                        return True
                except Exception:
                    pass

                if job.attempts < job.max_retries:
                    await job_service.update_job_status(
                        session,
                        job_id,
                        "pending",
                        error=str(e)[:1000],
                    )
                    logger.info(f"Worker {self.worker_id} job {job_id} retry {job.attempts}/{job.max_retries}")
                else:
                    await job_service.update_job_status(
                        session,
                        job_id,
                        "failed",
                        error=str(e)[:1000],
                    )
                    try:
                        await mission_service.update_mission(
                            session,
                            job.mission_id,
                            MissionUpdate(status=MissionStatus.failed),
                        )
                    except Exception:
                        pass

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

    async def _heartbeat_loop(self, job_id: uuid.UUID):
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                if not self._session_factory:
                    logger.debug(f"Worker {self.worker_id} no session_factory for heartbeat, skipping")
                    continue

                try:
                    async with self._session_factory() as hb_session:
                        await job_service.heartbeat_job(hb_session, job_id, self.worker_id)
                        await hb_session.commit()
                    logger.debug(f"Worker {self.worker_id} heartbeat committed for job {job_id}")

                except Exception as e:
                    error_str = str(e)
                    logger.warning(f"Worker {self.worker_id} heartbeat failed for {job_id}: {e}")

                    if "not owned" in error_str.lower() or "ownership" in error_str.lower() or "cancelled" in error_str.lower() or "completed" in error_str.lower() or "failed" in error_str.lower():
                        self._heartbeat_failed = True
                        self._heartbeat_failure_reason = error_str
                        logger.warning(
                            f"Worker {self.worker_id} heartbeat ownership lost for {job_id}: {error_str} - will stop unsafe continuation"
                        )
                        break
                    continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Worker {self.worker_id} heartbeat loop error: {e}")
                continue

    async def run_once(self, session: AsyncSession) -> Optional[uuid.UUID]:
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
        if session_factory:
            self._session_factory = session_factory

        self._running = True
        logger.info(f"Worker {self.worker_id} starting with poll_interval={self.poll_interval}s lease_timeout={self.lease_timeout}s")

        try:
            if self._session_factory:
                async with self._session_factory() as session:
                    recovered = await job_service.recover_stale_jobs(session, lease_timeout=self.lease_timeout)
                    if recovered:
                        logger.info(f"Worker {self.worker_id} recovered {len(recovered)} stale jobs on startup")
                        await session.commit()
        except Exception as e:
            logger.warning(f"Worker {self.worker_id} stale recovery on startup failed: {e}")

        while self._running:
            try:
                if self._session_factory:
                    async with self._session_factory() as session:
                        job_id = await self.run_once(session)
                        await session.commit()
                        if not job_id:
                            await asyncio.sleep(self.poll_interval)
                else:
                    await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Worker {self.worker_id} run_forever error: {e}")
                await asyncio.sleep(self.poll_interval)

        logger.info(f"Worker {self.worker_id} stopped")

    def stop(self):
        self._running = False


worker_service = MissionWorker()


async def recover_stale_jobs_on_startup(session: AsyncSession):
    try:
        recovered = await job_service.recover_stale_jobs(session, lease_timeout=LEASE_TIMEOUT_SECONDS)
        if recovered:
            logger.info(f"Recovered {len(recovered)} stale jobs on API startup")
        return recovered
    except Exception as e:
        logger.warning(f"Stale job recovery on API startup failed: {e}")
        return []
