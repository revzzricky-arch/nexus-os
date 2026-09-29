"""
Agent Runner Service - Phase 2B-3 Safe Stub

For this PR, task execution should be a SAFE STUB.
It may:
- create an agent_run
- move task to running
- simulate deterministic result
- emit task/agent events
- complete the task

It must NOT:
- execute arbitrary shell
- access host filesystem
- connect to arbitrary MCP servers
- perform unrestricted network calls
- bypass PermissionService
- use eval/exec/compile
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.task import Task
from app.models.agent import Agent, AgentRun
from app.schemas.event import EventCreate, EventType, EventSource
from app.services.event_bus import EventBusService
from app.core.exceptions import TaskNotFoundError


class AgentRunnerService:
    """
    AgentRunner abstraction - safe stub for Phase 2B-3
    """

    def __init__(self, event_bus: EventBusService):
        self.event_bus = event_bus

    async def run_task(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
        task_id: uuid.UUID,
        agent_type: str = "researcher",
    ) -> Dict[str, Any]:
        """
        Safe stub execution:
        - create agent_run
        - move task to running
        - simulate deterministic result
        - emit task/agent events
        - complete task
        """

        # Fetch task
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise TaskNotFoundError(task_id)

        # Fetch agent by type (reuse seeded agents)
        agent_result = await session.execute(select(Agent).where(Agent.type == agent_type))
        agent = agent_result.scalars().first()

        if not agent:
            # Create placeholder agent if not exists (for tests/dev without seeded agents)
            try:
                async with session.begin_nested():
                    agent = Agent(
                        id=uuid.uuid4(),
                        type=agent_type,
                        role=f"{agent_type.capitalize()}",
                        system_prompt_template=f"You are {agent_type}, {agent_type} agent.",
                        model_config={"provider": "deterministic", "model": "stub"},
                        tools=[],
                        capability_tags=[agent_type],
                    )
                    session.add(agent)
                    await session.flush()
            except Exception:
                # If creation fails due to unique constraint race, fetch again
                agent_result = await session.execute(select(Agent).where(Agent.type == agent_type))
                agent = agent_result.scalars().first()
                if not agent:
                    any_agent_result = await session.execute(select(Agent).limit(1))
                    agent = any_agent_result.scalars().first()

        agent_id = agent.id if agent else None

        if agent_id is None:
            # If still no agent, fetch any or create custom with nested transaction
            any_result = await session.execute(select(Agent).limit(1))
            any_agent = any_result.scalars().first()
            if any_agent:
                agent_id = any_agent.id
            else:
                try:
                    async with session.begin_nested():
                        fallback_agent = Agent(
                            id=uuid.uuid4(),
                            type="supervisor",
                            role="Supervisor",
                            system_prompt_template="Supervisor",
                            model_config={},
                            tools=[],
                            capability_tags=[],
                        )
                        session.add(fallback_agent)
                        await session.flush()
                        agent_id = fallback_agent.id
                except Exception:
                    # Last resort - should not happen
                    raise TaskNotFoundError(task_id, details={"reason": "No agent available for execution"})

        # Create agent_run
        agent_run = AgentRun(
            id=uuid.uuid4(),
            mission_id=mission_id,
            task_id=task_id,
            agent_id=agent_id,
            status="running",
            token_usage=0,
            cost_cents=0,
        )
        session.add(agent_run)
        await session.flush()

        # Emit agent_state_changed: idle -> running
        await self.event_bus.emit(
            session,
            EventCreate(
                type=EventType.agent_state_changed,
                source=EventSource.agent_runner,
                mission_id=mission_id,
                task_id=task_id,
                agent_id=agent_id,
                agent_run_id=agent_run.id,
                payload={
                    "from": "idle",
                    "to": "running",
                    "agent_type": agent_type,
                    "reason": f"Starting task {task.title}",
                },
            ),
        )

        # Move task to running
        from_status = task.status
        task.status = "running"
        task.updated_at = datetime.now(timezone.utc)
        await session.flush()

        await self.event_bus.emit(
            session,
            EventCreate(
                type=EventType.task_status_changed,
                source=EventSource.agent_runner,
                mission_id=mission_id,
                task_id=task_id,
                agent_id=agent_id,
                agent_run_id=agent_run.id,
                payload={
                    "from": from_status,
                    "to": "running",
                    "task_id": str(task_id),
                    "title": task.title,
                },
            ),
        )

        # Simulate deterministic result based on task title/type
        # No real LLM, no shell, no FS, no MCP, no network
        simulated_output = self._simulate_result(task, agent_type)

        # Complete task
        task.output = simulated_output
        task.status = "completed"
        task.token_usage = len(task.title) + len(task.description or "")  # deterministic token count
        task.cost_cents = 1  # minimal cost
        task.updated_at = datetime.now(timezone.utc)
        await session.flush()

        # Update agent_run
        agent_run.status = "completed"
        agent_run.token_usage = task.token_usage
        agent_run.cost_cents = task.cost_cents
        await session.flush()

        # Emit task_status_changed: running -> completed
        await self.event_bus.emit(
            session,
            EventCreate(
                type=EventType.task_status_changed,
                source=EventSource.agent_runner,
                mission_id=mission_id,
                task_id=task_id,
                agent_id=agent_id,
                agent_run_id=agent_run.id,
                payload={
                    "from": "running",
                    "to": "completed",
                    "task_id": str(task_id),
                    "title": task.title,
                },
            ),
        )

        # Emit agent_state_changed: running -> completed
        await self.event_bus.emit(
            session,
            EventCreate(
                type=EventType.agent_state_changed,
                source=EventSource.agent_runner,
                mission_id=mission_id,
                task_id=task_id,
                agent_id=agent_id,
                agent_run_id=agent_run.id,
                payload={
                    "from": "running",
                    "to": "completed",
                    "agent_type": agent_type,
                    "reason": f"Completed task {task.title}",
                },
            ),
        )

        # Emit cost_updated
        await self.event_bus.emit(
            session,
            EventCreate(
                type=EventType.cost_updated,
                source=EventSource.agent_runner,
                mission_id=mission_id,
                task_id=task_id,
                agent_id=agent_id,
                agent_run_id=agent_run.id,
                payload={
                    "task_id": str(task_id),
                    "token_usage": task.token_usage,
                    "cost_cents": task.cost_cents,
                    "total_tokens": task.token_usage,
                    "total_cost_cents": task.cost_cents,
                },
            ),
        )

        return {
            "task_id": str(task_id),
            "agent_run_id": str(agent_run.id),
            "status": "completed",
            "output": simulated_output,
            "token_usage": task.token_usage,
            "cost_cents": task.cost_cents,
        }

    def _simulate_result(self, task: Task, agent_type: str) -> Dict[str, Any]:
        """
        Deterministic simulation based on task title/type - no real execution
        """
        title_lower = task.title.lower()

        # Deterministic outputs per agent type
        if agent_type == "researcher":
            return {
                "type": "research",
                "summary": f"Research completed for: {task.title}",
                "findings": [f"Finding {i} for {task.title}" for i in range(1, 3)],
                "sources": [],
                "deterministic": True,
            }
        elif agent_type == "coder":
            return {
                "type": "code",
                "summary": f"Code implementation completed for: {task.title}",
                "files": [f"{task.title.lower().replace(' ', '_')}.py"],
                "tests_passed": True,
                "deterministic": True,
            }
        elif agent_type == "analyst":
            return {
                "type": "analysis",
                "summary": f"Analysis completed for: {task.title}",
                "insights": [f"Insight {i} for {task.title}" for i in range(1, 3)],
                "metrics": {"score": 0.95},
                "deterministic": True,
            }
        else:  # supervisor
            return {
                "type": "coordination",
                "summary": f"Coordination completed for: {task.title}",
                "decisions": [f"Decision {i} for {task.title}" for i in range(1, 2)],
                "deterministic": True,
            }

    async def get_agent_state(self, session: AsyncSession, agent_run_id: uuid.UUID) -> Dict[str, Any]:
        result = await session.execute(select(AgentRun).where(AgentRun.id == agent_run_id))
        run = result.scalar_one_or_none()
        if not run:
            return {"agent_run_id": str(agent_run_id), "state": "not_found"}
        return {
            "agent_run_id": str(run.id),
            "task_id": str(run.task_id),
            "agent_id": str(run.agent_id) if run.agent_id else None,
            "status": run.status,
            "token_usage": run.token_usage,
            "cost_cents": run.cost_cents,
        }


# Singleton with EventBus dependency
from app.services.event_bus import event_bus_service

agent_runner_service = AgentRunnerService(event_bus=event_bus_service)
