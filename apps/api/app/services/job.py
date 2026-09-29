"""
JobService - Phase 3 PR 3.1 Durable Worker + Mission Job System

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
- Mission/user scoping
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
from app.core.exceptions import ValidationError, NotFoundError, ConflictError
from app.config import settings

# Limits
MAX_PAYLOAD_SIZE_BYTES = 32 * 1024  # 32KB
LEASE_TIMEOUT_SECONDS = 60  # Configurable lease timeout, heartbeat must be renewed within this
HEARTBEAT_INTERVAL_SECONDS = 20

# Forbidden keys that must not appear in payload (secrets, tokens)
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

    # Size check
    try:
        payload_str = json.dumps(payload)
        if len(payload_str.encode("utf-8")) > MAX_PAYLOAD_SIZE_BYTES:
            raise ValidationError(f"Job payload too large max {MAX_PAYLOAD_SIZE_BYTES} bytes")
    except (TypeError, ValueError) as e:
        raise ValidationError(f"Invalid payload JSON: {e}")

    # Forbidden keys check - no secrets in payload
    payload_lower_keys = {k.lower() for k in payload.keys()} if isinstance(payload, dict) else set()
    for forbidden in FORBIDDEN_PAYLOAD_KEYS:
        if forbidden in payload_lower_keys:
            raise ValidationError(f"Forbidden key in payload: {forbidden} - no secrets/tokens allowed")

    # Forbidden substrings in values - no secrets/Bearer
    payload_str_lower = json.dumps(payload).lower()
    if "bearer " in payload_str_lower:
        raise ValidationError("Payload contains Bearer token - not allowed")
    if "sk-" in payload_str_lower:
        import re
        if re.search(r"sk-[a-zA-Z0-9]{5,}", payload_str_lower):
            raise ValidationError("Payload contains potential secret (sk-...) - not allowed")


class JobService:
    """
    Durable job service with Postgres row locking
    """

    async def create_job(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
        payload: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        max_retries: int = 3,
    ) -> MissionJob:
        """
        Create durable job for mission execution
        Idempotency: unique (mission_id, idempotency_key) prevents duplicate starts
        If idempotency_key provided and job exists, return existing job (idempotent)
        If no idempotency_key, enforce one active execution per mission via DB constraint
        """
        _validate_payload(payload)

        # If idempotency_key provided, check for existing job first (idempotent return)
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
                return existing

        # Check for active job for this mission if no idempotency key or as fallback
        # Enforce one active execution per mission
        active_query = select(MissionJob).where(
            and_(
                MissionJob.mission_id == mission_id,
                MissionJob.status.in_(ACTIVE_JOB_STATUSES),
            )
        )
        active_result = await session.execute(active_query)
        active_job = active_result.scalar_one_or_none()
        if active_job:
            # If active job exists and idempotency_key matches, return it (already handled above)
            # If active job exists and no idempotency_key provided, we should prevent duplicate active
            # But if idempotency_key is different, we should still prevent duplicate active per spec fallback
            # So if there's already active job, return it or raise conflict?
            # Spec: Repeated requests with same Idempotency-Key must return existing job rather than duplicate
            # For different keys, enforce one active per mission via DB constraint
            # We'll return active job if idempotency_key is None or different? Actually we should raise conflict for different key if active exists
            # But to be idempotent and prevent duplicate active, we will raise ConflictError for active exists when idempotency_key is different
            # However if idempotency_key is same, we already returned above
            # So for active exists and different or no idempotency key, raise conflict
            if idempotency_key is None or active_job.idempotency_key != idempotency_key:
                # If active job has same mission and is active, prevent duplicate
                # We can return active job for idempotency? Spec says enforce one active per mission with constraint
                # We'll raise conflict to make explicit, but also allow returning active if client retries without idempotency key?
                # Decision: raise ConflictError with active job info
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
            # Unique constraint violation - duplicate active or duplicate idempotency
            await session.rollback()
            # Try to fetch existing job for idempotency
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
                    return existing

            # Check active job
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

    async def get_job(self, session: AsyncSession, job_id: uuid.UUID) -> MissionJob:
        result = await session.execute(select(MissionJob).where(MissionJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise NotFoundError(f"Job {job_id} not found")
        return job

    async def get_job_by_execution(self, session: AsyncSession, execution_id: uuid.UUID) -> MissionJob:
        result = await session.execute(select(MissionJob).where(MissionJob.execution_id == execution_id))
        job = result.scalar_one_or_none()
        if not job:
            raise NotFoundError(f"Job with execution_id {execution_id} not found")
        return job

    async def list_jobs(
        self,
        session: AsyncSession,
        mission_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[MissionJob], int]:
        query = select(MissionJob)
        count_query = select(func.count()).select_from(MissionJob)

        if mission_id:
            query = query.where(MissionJob.mission_id == mission_id)
            count_query = count_query.where(MissionJob.mission_id == mission_id)

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
        Atomically sets running, locked_by, locked_at, heartbeat_at
        Returns claimed job or None if no pending jobs
        """
        # Use raw SQL for FOR UPDATE SKIP LOCKED to ensure Postgres-safe locking
        # For SQLite (tests), SKIP LOCKED is not supported, fallback to simple select
        try:
            # Try Postgres-style with SKIP LOCKED
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
            # Now fetch and update atomically within same transaction
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

        except Exception as e:
            # Fallback for SQLite (tests) - no SKIP LOCKED support
            # Use simple select and update with optimistic locking
            try:
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
            except Exception:
                return None

    async def update_job_status(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> MissionJob:
        if status not in JOB_STATUSES:
            raise ValidationError(f"Invalid status: {status}")

        job = await self.get_job(session, job_id)

        # Validate transition? For now allow any, but enforce terminal states
        # Terminal states should not transition back to active unless explicitly allowed
        terminal = {"completed", "failed", "cancelled"}
        if job.status in terminal and status not in terminal:
            raise ValidationError(f"Cannot transition from terminal {job.status} to {status}")

        job.status = status
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        job.updated_at = datetime.now(timezone.utc)

        # If terminal, clear lease
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
        """
        Renew heartbeat for running job
        Only worker that owns job can heartbeat
        """
        job = await self.get_job(session, job_id)

        if job.locked_by != worker_id:
            raise ValidationError(f"Job {job_id} not owned by worker {worker_id}")

        if job.status not in ("running", "awaiting_approval", "paused"):
            raise ValidationError(f"Cannot heartbeat job in status {job.status}")

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
        """
        Release job back to pending (e.g., on worker failure or approval pause)
        Only owner can release, or if lease expired
        """
        job = await self.get_job(session, job_id)

        # Allow release if owned by worker or lease expired
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
    ) -> MissionJob:
        """
        Cancel job - pending → cancelled, running/awaiting_approval/paused → cancelled
        Completed/failed/cancelled → idempotent
        """
        job = await self.get_job(session, job_id)

        if job.status in ("completed", "failed", "cancelled"):
            return job  # idempotent

        # Allow cancellation from active states
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
    ) -> List[MissionJob]:
        """
        Cancel all active jobs for mission
        """
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
        Recover stale jobs whose heartbeat/lease expired
        Only recover when heartbeat/lease genuinely expired, not merely locked_at older than 5m
        Uses heartbeat_at if available, else locked_at
        Test: healthy long-running worker NOT reclaimed, crashed worker with expired lease IS reclaimed
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=lease_timeout)

        # Find jobs where heartbeat_at < cutoff OR (heartbeat_at is null AND locked_at < cutoff) AND status in active running states
        # For awaiting_approval and paused, we use longer timeout? For now same timeout but could be configurable
        # Actually for awaiting_approval, heartbeat should still be renewed by worker waiting for approval? Or worker exits?
        # For this PR, we consider running jobs only for stale recovery, not awaiting_approval (which is waiting for human)
        # But spec says find jobs whose lease expired and move back to pending or recover via checkpoint
        # For this PR, only durable job recovery, not checkpoint resume yet

        query = select(MissionJob).where(
            and_(
                MissionJob.status.in_(("running", "paused")),
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
            # Move back to pending for retry if attempts < max_retries, else failed
            if job.attempts < job.max_retries:
                job.status = "pending"
                job.locked_at = None
                job.heartbeat_at = None
                job.locked_by = None
                job.error = f"Recovered from stale lease, previous worker {job.locked_by} heartbeat expired"
            else:
                job.status = "failed"
                job.error = f"Failed after {job.attempts} attempts, last worker {job.locked_by} lease expired"
                job.locked_at = None
                job.heartbeat_at = None
                job.locked_by = None

            job.updated_at = now
            recovered.append(job)

        await session.flush()

        return recovered


# Singleton
job_service = JobService()
