"""
Tasks Router - Phase 2B-2 minimal implementation
"""

from fastapi import APIRouter, Depends, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.dependencies import get_db, get_current_user
from app.schemas.task import TaskResponse
from app.models.task import Task
from app.core.exceptions import TaskNotFoundError, DomainError

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _handle_domain_error(e: DomainError):
    raise HTTPException(
        status_code=e.status_code,
        detail={"error": {"code": e.code, "message": e.message, "details": e.details}},
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID = Path(..., description="Task ID"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        _handle_domain_error(TaskNotFoundError(task_id))
    return task
