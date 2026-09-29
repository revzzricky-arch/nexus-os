"""
Checkpoint Abstraction - Phase 2B-3

Design graph so checkpointing can be added cleanly.
Use checkpoint abstraction, prefer PostgreSQL-backed checkpointing only if dependency/version stable and testable,
otherwise isolate checkpoint implementation behind interface and use deterministic test implementation.

Choice documented in ADR 015.

For this PR: use deterministic test implementation (InMemoryCheckpoint) behind interface.
PostgreSQL-backed checkpointing (langgraph-checkpoint-postgres) deferred to future PR when dependency stable and testable.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import uuid


class CheckpointService(ABC):
    """
    Checkpoint abstraction - isolates LangGraph checkpointing
    Allows clean replacement of backend (memory, postgres, etc.)
    """

    @abstractmethod
    async def save_checkpoint(self, thread_id: str, checkpoint: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def load_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def delete_checkpoint(self, thread_id: str) -> None:
        pass


class InMemoryCheckpoint(CheckpointService):
    """
    Deterministic test implementation - in-memory dict
    Safe for tests/dev, no external dependencies
    MVP-only and isolated behind interface for durable replacement later
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    async def save_checkpoint(self, thread_id: str, checkpoint: Dict[str, Any]) -> None:
        # Deterministic: store copy
        self._store[thread_id] = dict(checkpoint)

    async def load_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get(thread_id)

    async def delete_checkpoint(self, thread_id: str) -> None:
        self._store.pop(thread_id, None)

    def clear(self):
        self._store.clear()


class PostgresCheckpoint(CheckpointService):
    """
    PostgreSQL-backed checkpointing - placeholder for future
    Only use if langgraph-checkpoint-postgres dependency/version stable and testable

    Current choice: deferred, use InMemoryCheckpoint for Phase 2B-3
    Reason: Avoid fragile infrastructure, keep tests deterministic, no external DB required for checkpoint tests

    Future implementation would use:
    from langgraph.checkpoint.postgres import PostgresSaver
    or langgraph_checkpoint_postgres import PostgresSaver

    And wrap it behind this interface.
    """

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string
        self._fallback = InMemoryCheckpoint()
        # For now, fallback to in-memory
        # Real implementation would initialize PostgresSaver with connection_string

    async def save_checkpoint(self, thread_id: str, checkpoint: Dict[str, Any]) -> None:
        # TODO: Implement with PostgresSaver when stable
        # For Phase 2B-3, use fallback
        await self._fallback.save_checkpoint(thread_id, checkpoint)

    async def load_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        return await self._fallback.load_checkpoint(thread_id)

    async def delete_checkpoint(self, thread_id: str) -> None:
        await self._fallback.delete_checkpoint(thread_id)


def get_checkpoint_service(backend: str = "memory", connection_string: Optional[str] = None) -> CheckpointService:
    """
    Factory for checkpoint service
    backend: memory (deterministic test impl) or postgres (future)
    """
    if backend == "postgres":
        return PostgresCheckpoint(connection_string=connection_string)
    else:
        return InMemoryCheckpoint()


# Singleton for MVP - in-memory deterministic
checkpoint_service = get_checkpoint_service(backend="memory")
