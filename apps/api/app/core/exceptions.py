"""
Domain Exceptions - Phase 2B-2
Typed domain errors mapped to HTTP status codes
Consistent error format: {"error": {"code": "...", "message": "...", "details": {}}}
"""

from typing import Optional, Any


class DomainError(Exception):
    def __init__(self, code: str, message: str, details: Optional[dict] = None, status_code: int = 400):
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(message)


class MissionNotFoundError(DomainError):
    def __init__(self, mission_id: Any, details: Optional[dict] = None):
        super().__init__(
            code="mission_not_found",
            message=f"Mission {mission_id} not found",
            details=details or {"mission_id": str(mission_id)},
            status_code=404,
        )


class TaskNotFoundError(DomainError):
    def __init__(self, task_id: Any, details: Optional[dict] = None):
        super().__init__(
            code="task_not_found",
            message=f"Task {task_id} not found",
            details=details or {"task_id": str(task_id)},
            status_code=404,
        )


class EventNotFoundError(DomainError):
    def __init__(self, event_id: Any, details: Optional[dict] = None):
        super().__init__(
            code="event_not_found",
            message=f"Event {event_id} not found",
            details=details or {"event_id": str(event_id)},
            status_code=404,
        )


class InvalidTransitionError(DomainError):
    def __init__(self, from_status: str, to_status: str, details: Optional[dict] = None):
        super().__init__(
            code="invalid_transition",
            message=f"Invalid transition from {from_status} to {to_status}",
            details=details or {"from": from_status, "to": to_status},
            status_code=400,
        )


class ValidationError(DomainError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            code="validation_error",
            message=message,
            details=details or {},
            status_code=400,
        )


class UnauthorizedError(DomainError):
    def __init__(self, message: str = "Authentication required", details: Optional[dict] = None):
        super().__init__(
            code="unauthorized",
            message=message,
            details=details or {},
            status_code=401,
        )
