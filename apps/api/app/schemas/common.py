"""
Common schemas - pagination, error, timestamps, cost tracking
"""

from typing import Generic, TypeVar, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid

T = TypeVar("T")


class PaginationParams(BaseModel):
    limit: int = 20
    offset: int = 0


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    total: int
    limit: int
    offset: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Timestamps(BaseModel):
    created_at: datetime
    updated_at: Optional[datetime] = None


class CostTracking(BaseModel):
    token_usage: int = 0
    cost_cents: int = 0
