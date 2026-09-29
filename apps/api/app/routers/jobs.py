"""
Jobs Router - Phase 3 PR 3.1 Durable Worker
Fixes per PR #8 review:
- Enforce job API ownership / mission scoping via JobService ownership boundary
- Reuse Phase 2B-4 pattern: dev-user allowed, anonymous denied, future/non-dev must match mission.user_id
- Orphan/missing mission linkage fails closed
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.services.mission import mission_service
from app.services.job import job_service
from app.core.exceptions import DomainError

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _handle_domain_error(e: DomainError):
    raise HTTPException(
        status_code=e.status_code,
        detail={"error": {"code": e.code, "message": e.message, "details": e.details}},
    )


@router.get("/{job_id}", response_model=dict)
async def get_job(
    job_id: uuid.UUID = Path(..., description="Job ID"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        job = await job_service.get_job(db, job_id, user_context=user)
        return {
            "id": str(job.id),
            "mission_id": str(job.mission_id),
            "execution_id": str(job.execution_id),
            "idempotency_key": job.idempotency_key,
            "status": job.status,
            "attempts": job.attempts,
            "max_retries": job.max_retries,
            "payload": job.payload,
            "result": job.result,
            "error": job.error,
            "locked_by": job.locked_by,
            "locked_at": job.locked_at.isoformat() if job.locked_at else None,
            "heartbeat_at": job.heartbeat_at.isoformat() if job.heartbeat_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/{job_id}/cancel", response_model=dict)
async def cancel_job(
    job_id: uuid.UUID = Path(..., description="Job ID"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        job = await job_service.cancel_job(db, job_id, user_context=user)
        return {
            "id": str(job.id),
            "mission_id": str(job.mission_id),
            "execution_id": str(job.execution_id),
            "status": job.status,
        }
    except DomainError as e:
        _handle_domain_error(e)


mission_jobs_router = APIRouter(prefix="/missions", tags=["missions"])


@mission_jobs_router.get("/{mission_id}/jobs", response_model=dict)
async def list_mission_jobs(
    mission_id: uuid.UUID = Path(..., description="Mission ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        await mission_service.get_mission(db, mission_id)

        jobs, total = await job_service.list_jobs(
            db, mission_id=mission_id, status=status, limit=limit, offset=offset, user_context=user
        )

        data = [
            {
                "id": str(j.id),
                "mission_id": str(j.mission_id),
                "execution_id": str(j.execution_id),
                "idempotency_key": j.idempotency_key,
                "status": j.status,
                "attempts": j.attempts,
                "max_retries": j.max_retries,
                "locked_by": j.locked_by,
                "locked_at": j.locked_at.isoformat() if j.locked_at else None,
                "heartbeat_at": j.heartbeat_at.isoformat() if j.heartbeat_at else None,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "updated_at": j.updated_at.isoformat() if j.updated_at else None,
            }
            for j in jobs
        ]

        return {"data": data, "total": total, "limit": limit, "offset": offset}
    except DomainError as e:
        _handle_domain_error(e)
