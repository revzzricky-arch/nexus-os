"""
JobService - Phase 3 PR 3.1 Durable Worker + Mission Job System
Fixes:
- Heartbeat transaction isolation handled in worker (separate session)
- Ownership enforcement (Phase 2B-4 boundary)
- Recovery log preserves locked_by

Implements:
- create_job
- get_job
- list_jobs
- claim_job (SELECT ... FOR UPDATE SKIP LOCKED)
- update_job_status
- heartbeat_job
- release_job
- cancel_job
- recover_stale_jobs

Security:
- No secrets in payload
- No bearer token in payload/logs
- Validate payload size
- Mission/user scoping with ownership enforcement
- No arbitrary execution
- No eval/exec/compile/shell
"""

import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, text, func
from sqlalchemy.exc import IntegrityError

from app.models.job import MissionJob, JOB_STATUSES, ACTIVE_JOB_STATUSES
from app.models.mission import Mission
from app.core.exceptions import ValidationError, NotFoundError, ConflictError, PermissionDeniedError
from app.config import settings

# Limits
MAX_PAYLOAD_SIZE_BYTES = 32 * 1024  # 32KB
LEASE_TIMEOUT_SECONDS = 60
HEARTBEAT_INTERVAL_SECONDS = 20

FORBIDDEN_PAYLOAD_KEYS = {
    "token",
    "bearer_token",
    "nexus_dev_token",
    "api_key",
    "apikey",
    "password",
    "secret",
    "authorization",
    "auth",
    "credential",
}

FORBIDDEN_PAYLOAD_SUBSTRINGS = [
    "sk-",
    "Bearer ",
]


def _validate_payload(payload: Optional[Dict[str, Any]]) -> None:
    if payload is None:
        return
    try:
        payload_str = json.dumps(payload)
        if len(payload_str.encode("utf-8")) > MAX_PAYLOAD_SIZE_BYTES:
            raise ValidationError(f"Job payload too large max {MAX_PAYLOAD_SIZE_BYTES} bytes")
    except (TypeError, ValueError) as e:
        raise ValidationError(f"Invalid payload JSON: {e}")

    payload_lower_keys = {k.lower() for k in payload.keys()} if isinstance(payload, dict) else set()
    for forbidden in FORBIDDEN_PAYLOAD_KEYS:
        if forbidden in payload_lower_keys:
            raise ValidationError(f"Forbidden key in payload: {forbidden} - no secrets/tokens allowed")

    payload_str_lower = json.dumps(payload).lower()
    if "bearer " in payload_str_lower:
        raise ValidationError("Payload contains Bearer token - not allowed")
    if "sk-" in payload_str_lower:
        import re
        if re.search(r"sk-[a-zA-Z0-9]{5,}", payload_str_lower):
            raise ValidationError("Payload contains potential secret (sk-...) - not allowed")


class JobService:
    """
    Durable job service with Postgres row locking and ownership enforcement
    """

    def _get_user_id_from_context(self, user_context: Optional[Dict[str, Any]]) -> Optional[str]:
        if not user_context:
            return None
        if isinstance(user_context, dict):
            return user_context.get("user_id")
        return getattr(user_context, "user_id", None)

    def _is_uuid(self, val: str) -> bool:
        try:
            uuid.UUID(str(val))
            return True
        except ValueError:
            return False

    async def _check_mission_ownership(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Ownership enforcement - reuse Phase 2B-4 boundary
        - No user_context (internal service call) -> allow
        - dev-user -> allowed for MVP
        - anonymous -> denied
        - future/non-dev -> Mission.user_id must exactly match authenticated identity
        - missing mission linkage -> fail closed
        """
        user_id = self._get_user_id_from_context(user_context)
        if user_id is None:
            return
        if user_id == "dev-user":
            return
        if user_id == "anonymous":
            raise PermissionDeniedError("Anonymous user cannot access jobs")

        try:
            result = await session.execute(select(Mission).where(Mission.id == mission_id))
            mission = result.scalar_one_or_none()
        except Exception:
            raise PermissionDeniedError(f"Failed to verify mission ownership for {mission_id}")

        if not mission:
            raise PermissionDeniedError(f"Mission {mission_id} not found - orphan job denied")

        if not hasattr(mission, "user_id") or mission.user_id is None:
            raise PermissionDeniedError(f"No valid ownership match for mission {mission_id} - mission has no owner, non-dev user denied")

        try:
            mission_user_id_str = str(mission.user_id)
            context_user_id_str = str(user_id)
            if mission_user_id_str == context_user_id_str:
                return
            try:
                if uuid.UUID(mission_user_id_str) == uuid.UUID(context_user_id_str):
                    return
            except ValueError:
                pass
            raise PermissionDeniedError(f"Ownership mismatch for mission {mission_id} - user {user_id} does not own mission owned by {mission.user_id}")
        except PermissionDeniedError:
            raise
        except Exception:
            raise PermissionDeniedError(f"Failed to verify ownership for mission {mission_id}")

    async def _check_job_ownership(
        self,
        session: AsyncSession,
        job: MissionJob,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not job.mission_id:
            raise PermissionDeniedError("Job has no mission linkage - fail closed")
        await self._check_mission_ownership(session, job.mission_id, user_context)

    async def create_job(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
        payload: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        max_retries: int = 3,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> MissionJob:
        _validate_payload(payload)

        if user_context:
            await self._check_mission_ownership(session, mission_id, user_context)

        if idempotency_key:
            existing_query = select(MissionJob).where(
                and_(
                    MissionJob.mission_id == mission_id,
                    MissionJob.idempotency_key == idempotency_key,
                )
            )
            result = await session.execute(existing_query)
            existing = result.scalar_one_or_none()
            if existing:
                if user_context:
                    await self._check_job_ownership(session, existing, user_context)
                return existing

        active_query = select(MissionJob).where(
            and_(
                MissionJob.mission_id == mission_id,
                MissionJob.status.in_(ACTIVE_JOB_STATUSES),
            )
        )
        active_result = await session.execute(active_query)
        active_job = active_result.scalar_one_or_none()
        if active_job:
            if idempotency_key is None or active_job.idempotency_key != idempotency_key:
                raise ConflictError(
                    f"Mission {mission_id} already has active execution {active_job.execution_id} status {active_job.status}",
                    details={
                        "mission_id": str(mission_id),
                        "active_job_id": str(active_job.id),
                        "active_execution_id": str(active_job.execution_id),
                        "active_status": active_job.status,
                    },
                )

        execution_id = uuid.uuid4()

        job = MissionJob(
            id=uuid.uuid4(),
            mission_id=mission_id,
            execution_id=execution_id,
            idempotency_key=idempotency_key,
            status="pending",
            attempts=0,
            max_retries=max_retries,
            payload=payload or {},
            result=None,
            error=None,
            locked_at=None,
            heartbeat_at=None,
            locked_by=None,
        )

        session.add(job)
        try:
            await session.flush()
            await session.refresh(job)
        except IntegrityError as e:
            await session.rollback()
            if idempotency_key:
                existing_query = select(MissionJob).where(
                    and_(
                        MissionJob.mission_id == mission_id,
                        MissionJob.idempotency_key == idempotency_key,
                    )
                )
                result = await session.execute(existing_query)
                existing = result.scalar_one_or_none()
                if existing:
                    if user_context:
                        await self._check_job_ownership(session, existing, user_context)
                    return existing

            active_query = select(MissionJob).where(
                and_(
                    MissionJob.mission_id == mission_id,
                    MissionJob.status.in_(ACTIVE_JOB_STATUSES),
                )
            )
            active_result = await session.execute(active_query)
            active_job = active_result.scalar_one_or_none()
            if active_job:
                raise ConflictError(
                    f"Mission {mission_id} already has active execution",
                    details={
                        "mission_id": str(mission_id),
                        "active_job_id": str(active_job.id),
                        "active_execution_id": str(active_job.execution_id),
                    },
                )

            raise ValidationError(f"Failed to create job: {e}")

        return job

    async def get_job(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> MissionJob:
        result = await session.execute(select(MissionJob).where(MissionJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise NotFoundError(f"Job {job_id} not found")
        await self._check_job_ownership(session, job, user_context)
        return job

    async def get_job_by_execution(
        self,
        session: AsyncSession,
        execution_id: uuid.UUID,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> MissionJob:
        result = await session.execute(select(MissionJob).where(MissionJob.execution_id == execution_id))
        job = result.scalar_one_or_none()
        if not job:
            raise NotFoundError(f"Job with execution_id {execution_id} not found")
        await self._check_job_ownership(session, job, user_context)
        return job

    async def list_jobs(
        self,
        session: AsyncSession,
        mission_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[MissionJob], int]:
        user_id = self._get_user_id_from_context(user_context)
        if user_id == "anonymous":
            raise PermissionDeniedError("Anonymous user cannot list jobs")

        if mission_id and user_context:
            await self._check_mission_ownership(session, mission_id, user_context)

        query = select(MissionJob)
        count_query = select(func.count()).select_from(MissionJob)

        if mission_id:
            query = query.where(MissionJob.mission_id == mission_id)
            count_query = count_query.where(MissionJob.mission_id == mission_id)
        else:
            if user_id and user_id not in ("dev-user", None):
                try:
                    if self._is_uuid(user_id):
                        uid = uuid.UUID(str(user_id))
                        query = query.join(Mission, MissionJob.mission_id == Mission.id).where(Mission.user_id == uid)
                        count_query = count_query.join(Mission, MissionJob.mission_id == Mission.id).where(Mission.user_id == uid)
                    else:
                        return [], 0
                except Exception:
                    return [], 0

        if status:
            if status not in JOB_STATUSES:
                raise ValidationError(f"Invalid status filter: {status}")
            query = query.where(MissionJob.status == status)
            count_query = count_query.where(MissionJob.status == status)

        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(MissionJob.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(query)
        jobs = result.scalars().all()

        return list(jobs), total

    async def claim_job(
        self,
        session: AsyncSession,
        worker_id: str,
        lease_timeout: int = LEASE_TIMEOUT_SECONDS,
    ) -> Optional[MissionJob]:
        """
        Claim pending job using SELECT ... FOR UPDATE SKIP LOCKED
        - PostgreSQL: use SKIP LOCKED and propagate database errors (do NOT fallback silently)
        - SQLite: use simplified fallback only because test/dev compatibility
        - Unknown dialects: fail closed rather than unlocked claim
        Uses session/engine dialect to select path explicitly.
        """
        # Determine dialect explicitly
        dialect_name = ""
        try:
            bind = session.get_bind()
            if bind is not None:
                dialect_name = getattr(bind.dialect, "name", "") or ""
            else:
                # Fallback try session.bind
                b = getattr(session, "bind", None)
                if b is not None:
                    dialect_name = getattr(b.dialect, "name", "") or ""
        except Exception:
            dialect_name = ""

        dialect_name = dialect_name.lower()

        is_postgres = "postgres" in dialect_name or "pg" == dialect_name
        # Only explicit sqlite/aiosqlite allowed for test/dev fallback
        # Empty/unknown/unsupported must FAIL CLOSED per required rule
        is_sqlite = "sqlite" in dialect_name or "aiosqlite" in dialect_name

        # For explicit postgres, use SKIP LOCKED and propagate errors (do NOT fallback silently)
        if is_postgres and not is_sqlite:
            # PostgreSQL path - propagate database errors, do NOT use broad fallback
            query = text(
                """
                SELECT id FROM mission_jobs
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """
            )
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                return None

            job_id = row[0]
            job_query = select(MissionJob).where(MissionJob.id == job_id).with_for_update()
            job_result = await session.execute(job_query)
            job = job_result.scalar_one_or_none()
            if not job or job.status != "pending":
                return None

            now = datetime.now(timezone.utc)
            job.status = "running"
            job.locked_by = worker_id
            job.locked_at = now
            job.heartbeat_at = now
            job.attempts += 1
            job.updated_at = now

            await session.flush()
            await session.refresh(job)

            return job

        elif is_sqlite:
            # SQLite fallback only for test/dev compatibility
            query = select(MissionJob).where(MissionJob.status == "pending").order_by(MissionJob.created_at.asc()).limit(1)
            result = await session.execute(query)
            job = result.scalar_one_or_none()
            if not job:
                return None

            now = datetime.now(timezone.utc)
            job.status = "running"
            job.locked_by = worker_id
            job.locked_at = now
            job.heartbeat_at = now
            job.attempts += 1
            job.updated_at = now

            await session.flush()
            await session.refresh(job)

            return job
        else:
            # Unknown/unsupported dialect - fail closed rather than silently using unlocked claim
            raise ValidationError(f"Unsupported dialect {dialect_name} for claim_job - fail closed")

    async def update_job_status(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        expected_locked_by: Optional[str] = None,
        expected_status: Optional[str] = None,
    ) -> MissionJob:
        """
        Update job status with terminal immutability and optional fencing.

        Terminal states completed/failed/cancelled are immutable once reached, except idempotent same-state.
        Rejects:
          cancelled -> completed, cancelled -> failed,
          completed -> failed, completed -> cancelled,
          failed -> completed, failed -> cancelled

        For worker finalization, pass expected_locked_by and expected_status to enable atomic conditional UPDATE:
          WHERE id = job_id AND status = expected_status AND locked_by = expected_locked_by
        If zero rows updated, re-read authoritative job and do not overwrite cancelled/completed/failed or different owner.
        """
        if status not in JOB_STATUSES:
            raise ValidationError(f"Invalid status: {status}")

        terminal = {"completed", "failed", "cancelled"}

        # If fencing parameters provided, use atomic fencing to eliminate TOCTOU race
        # Preferred: conditional UPDATE WHERE id AND status AND locked_by, check rowcount
        # Implementation: SELECT FOR UPDATE + fencing checks + ORM update (Postgres lock ensures atomicity, SQLite fallback checks)
        if expected_locked_by is not None or expected_status is not None:
            import logging

            logger = logging.getLogger(__name__)
            now = datetime.now(timezone.utc)

            # First, get current job with FOR UPDATE to lock row (Postgres) and check terminal immutability
            res = await session.execute(
                select(MissionJob).where(MissionJob.id == job_id).with_for_update()
            )
            fresh = res.scalar_one_or_none()
            if not fresh:
                raise NotFoundError(f"Job {job_id} not found")

            # Terminal immutability check
            if fresh.status in terminal:
                if fresh.status != status:
                    logger.info(
                        f"Job {job_id} already in terminal {fresh.status}, not overwriting with {status} (fencing)"
                    )
                    return fresh
                else:
                    return fresh

            # Ownership fencing
            if expected_locked_by is not None and fresh.locked_by != expected_locked_by:
                logger.info(
                    f"Job {job_id} ownership changed from {expected_locked_by} to {fresh.locked_by}, not overwriting with {status}"
                )
                return fresh

            # Status fencing
            if expected_status is not None and fresh.status != expected_status:
                logger.info(
                    f"Job {job_id} status changed from expected {expected_status} to {fresh.status}, not overwriting with {status}"
                )
                return fresh

            # All fencing checks passed - perform update via ORM (row is locked in Postgres, checked in SQLite)
            # Use direct ORM update to avoid aiosqlite rowcount/connection issues in Python 3.12
            fresh.status = status
            if result is not None:
                fresh.result = result
            if error is not None:
                fresh.error = error
            fresh.updated_at = now

            if status in terminal:
                fresh.locked_at = None
                fresh.heartbeat_at = None
                fresh.locked_by = None

            await session.flush()
            await session.refresh(fresh)
            return fresh

        # Non-fencing path: enforce terminal immutability
        res = await session.execute(select(MissionJob).where(MissionJob.id == job_id))
        job = res.scalar_one_or_none()
        if not job:
            raise NotFoundError(f"Job {job_id} not found")

        if job.status in terminal:
            if job.status != status:
                raise ValidationError(
                    f"Cannot transition from terminal {job.status} to {status} - terminal states immutable (allowed only idempotent same-state)",
                    details={"from": job.status, "to": status, "job_id": str(job_id)},
                )
            else:
                # Idempotent same-state terminal update - return as-is
                return job

        job.status = status
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        job.updated_at = datetime.now(timezone.utc)

        if status in terminal:
            job.locked_at = None
            job.heartbeat_at = None
            job.locked_by = None

        await session.flush()
        await session.refresh(job)

        return job

    async def heartbeat_job(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        worker_id: str,
    ) -> MissionJob:
        result = await session.execute(select(MissionJob).where(MissionJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise NotFoundError(f"Job {job_id} not found")

        if job.locked_by != worker_id:
            raise ValidationError(f"Job {job_id} not owned by worker {worker_id} - ownership lost")

        if job.status not in ("running", "awaiting_approval", "paused"):
            raise ValidationError(f"Cannot heartbeat job in status {job.status} - job cancelled or completed")

        now = datetime.now(timezone.utc)
        job.heartbeat_at = now
        job.updated_at = now

        await session.flush()
        await session.refresh(job)

        return job

    async def release_job(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        worker_id: str,
    ) -> MissionJob:
        res = await session.execute(select(MissionJob).where(MissionJob.id == job_id))
        job = res.scalar_one_or_none()
        if not job:
            raise NotFoundError(f"Job {job_id} not found")

        now = datetime.now(timezone.utc)
        lease_expired = False
        if job.heartbeat_at:
            lease_expired = (now - job.heartbeat_at).total_seconds() > LEASE_TIMEOUT_SECONDS
        elif job.locked_at:
            lease_expired = (now - job.locked_at).total_seconds() > LEASE_TIMEOUT_SECONDS

        if job.locked_by != worker_id and not lease_expired:
            raise ValidationError(f"Cannot release job not owned by {worker_id} and lease not expired")

        job.status = "pending"
        job.locked_at = None
        job.heartbeat_at = None
        job.locked_by = None
        job.updated_at = now

        await session.flush()
        await session.refresh(job)

        return job

    async def cancel_job(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> MissionJob:
        res = await session.execute(select(MissionJob).where(MissionJob.id == job_id))
        job = res.scalar_one_or_none()
        if not job:
            raise NotFoundError(f"Job {job_id} not found")

        await self._check_job_ownership(session, job, user_context)

        if job.status in ("completed", "failed", "cancelled"):
            return job

        if job.status not in ACTIVE_JOB_STATUSES:
            raise ValidationError(f"Cannot cancel job in status {job.status}")

        job.status = "cancelled"
        job.locked_at = None
        job.heartbeat_at = None
        job.locked_by = None
        job.updated_at = datetime.now(timezone.utc)

        await session.flush()
        await session.refresh(job)

        return job

    async def cancel_jobs_for_mission(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> List[MissionJob]:
        if user_context:
            await self._check_mission_ownership(session, mission_id, user_context)

        query = select(MissionJob).where(
            and_(
                MissionJob.mission_id == mission_id,
                MissionJob.status.in_(ACTIVE_JOB_STATUSES),
            )
        )
        result = await session.execute(query)
        jobs = result.scalars().all()

        cancelled = []
        for job in jobs:
            job.status = "cancelled"
            job.locked_at = None
            job.heartbeat_at = None
            job.locked_by = None
            job.updated_at = datetime.now(timezone.utc)
            cancelled.append(job)

        await session.flush()

        return cancelled

    async def recover_stale_jobs(
        self,
        session: AsyncSession,
        lease_timeout: int = LEASE_TIMEOUT_SECONDS,
    ) -> List[MissionJob]:
        """
        Recover stale jobs whose lease expired.

        Exact rule for PR 3.1:
        - Only 'running' jobs with expired lease may recover (crashed worker)
        - 'paused' jobs intentionally paused by user/system must remain paused unless explicit recovery reason
          -> Do NOT auto-convert paused to pending merely because heartbeat is old
        - 'awaiting_approval' must NOT be treated as crashed running job in this PR because approval resume/checkpointing
          is deferred to PR 3.2/3.6
        - Healthy long-running worker with recent heartbeat NOT reclaimed, crashed expired IS reclaimed

        Preserves previous locked_by in error message.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=lease_timeout)

        query = select(MissionJob).where(
            and_(
                MissionJob.status.in_(("running",)),  # Only running, not paused, not awaiting_approval
                or_(
                    and_(MissionJob.heartbeat_at.is_not(None), MissionJob.heartbeat_at < cutoff),
                    and_(MissionJob.heartbeat_at.is_(None), MissionJob.locked_at.is_not(None), MissionJob.locked_at < cutoff),
                ),
            )
        )

        result = await session.execute(query)
        stale_jobs = result.scalars().all()

        recovered = []
        for job in stale_jobs:
            previous_worker = job.locked_by

            if job.attempts < job.max_retries:
                job.status = "pending"
                job.error = f"Recovered from stale lease, previous worker {previous_worker} heartbeat expired"
                job.locked_at = None
                job.heartbeat_at = None
                job.locked_by = None
            else:
                job.status = "failed"
                job.error = f"Failed after {job.attempts} attempts, last worker {previous_worker} lease expired"
                job.locked_at = None
                job.heartbeat_at = None
                job.locked_by = None

            job.updated_at = now
            recovered.append(job)

        await session.flush()

        return recovered


job_service = JobService()
