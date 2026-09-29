"""
Orchestrator Service - Phase 2B-3 Supervisor + LangGraph Runtime Foundation

Builds first real orchestration pipeline:
Mission API → SupervisorService → MissionPlan → DAG validation/planning → Agent assignment → LangGraph execution → Task execution stub → Mission finalization → EventBus

Uses existing MissionService for status changes so EventBus emits proper events.
Uses service boundary that can later be replaced by durable worker (MVP execution mechanism documented in ADR).
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.mission import Mission
from app.models.task import Task, TaskDependency
from app.schemas.mission import MissionStatus
from app.schemas.event import EventCreate, EventType, EventSource
from app.services.mission import MissionService
from app.services.supervisor import supervisor_service
from app.services.agent_runner import agent_runner_service
from app.services.event_bus import EventBusService
from app.core.dag import validate_and_plan_dag, DAGValidationError
from app.core.langgraph.graph import get_mission_graph
from app.core.langgraph.state import MissionState
from app.core.exceptions import MissionNotFoundError, ValidationError


class OrchestratorService:
    """
    Orchestrator that runs mission via Supervisor + LangGraph + AgentRunner stub
    MVP execution mechanism: synchronous within request for now, but isolated behind service boundary
    so it can be replaced by durable worker/queue later (documented in ADR 015).
    """

    def __init__(self, mission_service: MissionService, event_bus: EventBusService):
        self.mission_service = mission_service
        self.event_bus = event_bus
        self.supervisor = supervisor_service
        self.agent_runner = agent_runner_service

    async def start_mission(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Start mission execution:
        - verify mission exists
        - verify valid starting state (draft, planned, failed can be restarted? For this PR: draft, planned, failed allowed)
        - invoke Supervisor/LangGraph orchestration
        - transition mission through proper lifecycle draft→decomposing→planned→running→completed or failed
        - return mission execution info
        """

        # Verify mission exists
        mission = await self.mission_service.get_mission(session, mission_id)

        # Verify valid starting state
        # For Phase 2B-3, allow start from draft, planned, failed, paused
        # draft is initial, planned means already decomposed but not yet running
        valid_start_states = ["draft", "planned", "failed", "paused"]
        if mission.status not in valid_start_states:
            raise ValidationError(
                f"Cannot start mission from status {mission.status}",
                details={"mission_id": str(mission_id), "current_status": mission.status, "valid_start_states": valid_start_states},
            )

        try:
            # Transition: draft → decomposing
            # Use MissionService so EventBus emits mission_status_changed
            if mission.status == "draft":
                from app.schemas.mission import MissionUpdate

                mission = await self.mission_service.update_mission(
                    session, mission_id, MissionUpdate(status=MissionStatus.decomposing)
                )

            # Decompose mission via Supervisor
            plan = await self.supervisor.decompose_mission(
                mission_id=mission_id,
                goal=mission.goal,
                template=mission.template,
                title=mission.title,
            )

            # Validate DAG and create tasks
            dag_tasks = [
                {"id": t.id or t.title.lower().replace(" ", "_"), "title": t.title, "dependencies": t.dependencies}
                for t in plan.tasks
            ]

            dag_result = validate_and_plan_dag(dag_tasks)

            # Store DAG on mission
            mission.dag = {
                "nodes": dag_result.nodes,
                "edges": dag_result.edges,
                "layers": dag_result.layers,
                "topological_order": dag_result.topological_order,
            }
            await session.flush()

            # Ensure agents exist (seed if needed for tests/dev)
            from app.models.agent import Agent

            for agent_type in ["supervisor", "researcher", "coder", "analyst"]:
                existing_agent_result = await session.execute(select(Agent).where(Agent.type == agent_type))
                existing_agent = existing_agent_result.scalars().first()
                if not existing_agent:
                    try:
                        async with session.begin_nested():
                            new_agent = Agent(
                                id=uuid.uuid4(),
                                type=agent_type,
                                role=f"{agent_type.capitalize()}",
                                system_prompt_template=f"You are {agent_type} agent, {agent_type} capabilities.",
                                model_config={"provider": "deterministic", "model": "stub"},
                                tools=[],
                                capability_tags=[agent_type],
                            )
                            session.add(new_agent)
                            await session.flush()
                    except Exception:
                        # Unique constraint race or other, ignore and continue
                        pass

            # Create task records from MissionPlan
            # Clear existing tasks if any (for restart)
            existing_tasks_result = await session.execute(select(Task).where(Task.mission_id == mission_id))
            existing_tasks = existing_tasks_result.scalars().all()
            for t in existing_tasks:
                await session.delete(t)
            await session.flush()

            # Create new tasks
            task_id_map = {}  # temp id -> real UUID
            created_tasks = []

            for plan_task in plan.tasks:
                temp_id = plan_task.id or plan_task.title.lower().replace(" ", "_")
                real_id = uuid.uuid4()
                task_id_map[temp_id] = real_id

                task = Task(
                    id=real_id,
                    mission_id=mission_id,
                    title=plan_task.title,
                    description=plan_task.description,
                    agent_type=plan_task.agent_type,
                    status="pending",
                    input=plan_task.input,
                    output=None,
                )
                session.add(task)
                created_tasks.append(task)

            await session.flush()

            # Store dependency relationships
            for plan_task in plan.tasks:
                temp_id = plan_task.id or plan_task.title.lower().replace(" ", "_")
                real_id = task_id_map[temp_id]

                for dep_temp_id in plan_task.dependencies:
                    dep_real_id = task_id_map.get(dep_temp_id)
                    if dep_real_id:
                        dep = TaskDependency(
                            id=uuid.uuid4(),
                            task_id=real_id,
                            depends_on_task_id=dep_real_id,
                        )
                        session.add(dep)

            await session.flush()

            # Transition: decomposing → planned
            from app.schemas.mission import MissionUpdate

            mission = await self.mission_service.update_mission(
                session, mission_id, MissionUpdate(status=MissionStatus.planned)
            )

            # Transition: planned → running
            mission = await self.mission_service.update_mission(
                session, mission_id, MissionUpdate(status=MissionStatus.running)
            )

            # Execute via LangGraph (state transitions) + AgentRunner (real DB tasks)
            # Build initial state
            initial_state: MissionState = {
                "mission_id": str(mission_id),
                "goal": mission.goal,
                "title": mission.title,
                "template": mission.template,
                "status": "running",
                "tasks": [
                    {
                        "id": str(task_id_map[t.id or t.title.lower().replace(" ", "_")]),
                        "title": t.title,
                        "description": t.description,
                        "agent_type": t.agent_type,
                        "status": "pending",
                        "dependencies": t.dependencies,
                        "output": None,
                        "error": None,
                        "agent_run_id": None,
                        "token_usage": 0,
                        "cost_cents": 0,
                    }
                    for t in plan.tasks
                ],
                "dag": mission.dag,
                "agent_assignments": {},
                "agent_runs": [],
                "messages": [],
                "approvals_pending": [],
                "total_tokens": 0,
                "total_cost_cents": 0,
                "cost_breakdown": {},
                "error": None,
                "error_details": None,
                "next_action": "decompose",
                "metadata": {"template": mission.template},
                "current_task_id": None,
                "completed_tasks": [],
                "failed_tasks": [],
            }

            # Run LangGraph - for Phase 2B-3, this is deterministic and safe
            # The graph will go through decompose→plan_dag→assign→execute_task→finalize
            # For this PR, we use the graph to validate state transitions, but actual task execution
            # is done via AgentRunner below with real DB session
            graph = get_mission_graph()

            # Note: LangGraph execution is synchronous in terms of state transitions for this MVP
            # It does not block indefinitely - each node is quick and deterministic
            # This is the MVP execution mechanism that can later be replaced by durable worker
            final_state = None
            async for event in graph.astream(initial_state):
                # event is dict with node name -> state update
                # We track final state
                for node_name, node_state in event.items():
                    final_state = node_state
                    # Could emit events here for observability

            # Now execute tasks via AgentRunner in topological order (real DB)
            # This is the safe stub execution that creates agent_runs, moves tasks, emits events
            topo_order = mission.dag.get("topological_order", [])

            # Map temp ids to real ids for execution
            # topo_order contains temp ids from plan, need to map to real task ids
            for temp_id in topo_order:
                real_id = task_id_map.get(temp_id)
                if not real_id:
                    continue

                # Find task and its agent type
                plan_task = next((t for t in plan.tasks if (t.id or t.title.lower().replace(" ", "_")) == temp_id), None)
                if not plan_task:
                    continue

                try:
                    await self.agent_runner.run_task(
                        session=session,
                        mission_id=mission_id,
                        task_id=real_id,
                        agent_type=plan_task.agent_type,
                    )
                except Exception as e:
                    # On task failure, emit error event and fail mission
                    await self.event_bus.emit(
                        session,
                        EventCreate(
                            type=EventType.error,
                            source=EventSource.agent_runner,
                            mission_id=mission_id,
                            task_id=real_id,
                            payload={
                                "message": f"Task {plan_task.title} failed: {str(e)[:500]}",
                                "code": "task_execution_failed",
                                "task_id": str(real_id),
                            },
                        ),
                    )
                    # Transition to failed
                    mission = await self.mission_service.update_mission(
                        session, mission_id, MissionUpdate(status=MissionStatus.failed)
                    )
                    return {
                        "mission_id": str(mission_id),
                        "status": "failed",
                        "error": str(e),
                        "completed_tasks": len([t for t in created_tasks if t.status == "completed"]),
                        "total_tasks": len(created_tasks),
                    }

            # All tasks completed - finalize mission
            mission = await self.mission_service.update_mission(
                session, mission_id, MissionUpdate(status=MissionStatus.completed)
            )

            # Emit handoff event for completion (example of handoff event)
            await self.event_bus.emit(
                session,
                EventCreate(
                    type=EventType.handoff,
                    source=EventSource.supervisor,
                    mission_id=mission_id,
                    payload={
                        "from_agent": None,
                        "to_agent": None,
                        "task_id": None,
                        "summary": f"Mission {mission.title} completed with {len(created_tasks)} tasks",
                    },
                ),
            )

            return {
                "mission_id": str(mission_id),
                "status": mission.status,
                "total_tasks": len(created_tasks),
                "completed_tasks": len(created_tasks),
                "dag": mission.dag,
                "final_state": final_state,
            }

        except DAGValidationError as e:
            # DAG invalid - fail mission
            from app.schemas.mission import MissionUpdate

            await self.event_bus.emit(
                session,
                EventCreate(
                    type=EventType.error,
                    source=EventSource.supervisor,
                    mission_id=mission_id,
                    payload={"message": e.message, "code": "dag_validation_failed", "details": e.details},
                ),
            )

            mission = await self.mission_service.update_mission(
                session, mission_id, MissionUpdate(status=MissionStatus.failed)
            )

            return {
                "mission_id": str(mission_id),
                "status": "failed",
                "error": e.message,
                "details": e.details,
            }

        except Exception as e:
            # Generic failure - fail mission
            from app.schemas.mission import MissionUpdate

            await self.event_bus.emit(
                session,
                EventCreate(
                    type=EventType.error,
                    source=EventSource.system,
                    mission_id=mission_id,
                    payload={"message": str(e)[:500], "code": "mission_execution_failed"},
                ),
            )

            try:
                mission = await self.mission_service.update_mission(
                    session, mission_id, MissionUpdate(status=MissionStatus.failed)
                )
            except Exception:
                pass  # If update fails, still return error

            return {
                "mission_id": str(mission_id),
                "status": "failed",
                "error": str(e)[:500],
            }


# Singleton
from app.services.mission import mission_service
from app.services.event_bus import event_bus_service

orchestrator_service = OrchestratorService(mission_service=mission_service, event_bus=event_bus_service)
