"""
Supervisor Service - Phase 2B-3 Supervisor + LangGraph Runtime Foundation

Implements clean SupervisorService abstraction with provider-independent deterministic fallback
Reuse existing ModelProvider abstraction, do not hardcode vendor logic, structured MissionPlan output, Pydantic validation, no API key required for tests
"""

import uuid
from typing import Optional, List, Dict, Any
from pydantic import ValidationError as PydanticValidationError

from app.schemas.mission import MissionPlan, MissionPlanTask, MissionTemplate, MissionDAG
from app.core.model_provider import get_model_provider, ChatMessage
from app.config import settings
from app.core.dag import validate_and_plan_dag, DAGValidationError


# Deterministic fallback templates - concise and configuration-driven
FALLBACK_PLANS = {
    "research": [
        {"title": "Research Objective", "description": "Gather information and context for: {goal}", "agent_type": "researcher", "dependencies": []},
        {"title": "Analyze Findings", "description": "Analyze research results and extract insights", "agent_type": "analyst", "dependencies": ["research_objective"]},
        {"title": "Synthesize Report", "description": "Create final report with recommendations", "agent_type": "supervisor", "dependencies": ["analyze_findings"]},
    ],
    "code": [
        {"title": "Design Solution", "description": "Design technical solution for: {goal}", "agent_type": "supervisor", "dependencies": []},
        {"title": "Implement Code", "description": "Implement core functionality", "agent_type": "coder", "dependencies": ["design_solution"]},
        {"title": "Test Implementation", "description": "Create tests and validate implementation", "agent_type": "coder", "dependencies": ["implement_code"]},
        {"title": "Review and Document", "description": "Review code and create documentation", "agent_type": "analyst", "dependencies": ["test_implementation"]},
    ],
    "analysis": [
        {"title": "Collect Data", "description": "Collect relevant data for analysis: {goal}", "agent_type": "researcher", "dependencies": []},
        {"title": "Process Data", "description": "Clean and process collected data", "agent_type": "analyst", "dependencies": ["collect_data"]},
        {"title": "Perform Analysis", "description": "Run analysis and generate insights", "agent_type": "analyst", "dependencies": ["process_data"]},
        {"title": "Create Visualization", "description": "Create charts and summary", "agent_type": "supervisor", "dependencies": ["perform_analysis"]},
    ],
    "general": [
        {"title": "Understand Goal", "description": "Break down goal: {goal}", "agent_type": "supervisor", "dependencies": []},
        {"title": "Execute Task", "description": "Execute main objective", "agent_type": "researcher", "dependencies": ["understand_goal"]},
        {"title": "Finalize", "description": "Review and finalize results", "agent_type": "supervisor", "dependencies": ["execute_task"]},
    ],
}


def _generate_deterministic_plan(goal: str, template: str, mission_id: Optional[uuid.UUID] = None) -> MissionPlan:
    """
    Deterministic fallback planner - no LLM required, safe for tests/dev
    Creates simple plans for research/code/analysis/general
    """
    template_key = template if template in FALLBACK_PLANS else "general"
    task_templates = FALLBACK_PLANS[template_key]

    tasks = []
    for tmpl in task_templates:
        # Replace {goal} placeholder
        description = tmpl["description"].format(goal=goal)
        # Generate deterministic id from title
        task_id = tmpl["title"].lower().replace(" ", "_")
        tasks.append(
            MissionPlanTask(
                id=task_id,
                title=tmpl["title"],
                description=description,
                agent_type=tmpl["agent_type"],
                dependencies=tmpl["dependencies"],
                metadata={"template": template_key, "fallback": True},
            )
        )

    # Validate DAG
    dag_tasks = [{"id": t.id, "title": t.title, "dependencies": t.dependencies} for t in tasks]
    try:
        dag_result = validate_and_plan_dag(dag_tasks)
        dag = MissionDAG(
            nodes=dag_result.nodes,
            edges=dag_result.edges,
            layers=dag_result.layers,
            topological_order=dag_result.topological_order,
        )
    except DAGValidationError as e:
        # Fallback should never have cycle, but handle
        dag = MissionDAG(nodes=[t.id for t in tasks], edges=[], layers={}, topological_order=[t.id for t in tasks])

    return MissionPlan(
        mission_id=mission_id,
        goal=goal,
        template=MissionTemplate(template_key),
        tasks=tasks,
        dag=dag,
        metadata={"fallback": True, "template": template_key},
    )


class SupervisorService:
    """
    Supervisor Service abstraction - provider-independent
    """

    def __init__(self, model_provider_name: Optional[str] = None):
        self.model_provider_name = model_provider_name or settings.model_default_provider
        self._provider = None

    def _get_provider(self):
        """Lazy provider initialization"""
        if self._provider is None:
            try:
                self._provider = get_model_provider(self.model_provider_name)
            except Exception:
                self._provider = None
        return self._provider

    async def decompose_mission(
        self,
        mission_id: uuid.UUID,
        goal: str,
        template: str = "general",
        title: Optional[str] = None,
    ) -> MissionPlan:
        """
        Decompose mission into MissionPlan
        - Provider-independent
        - Reuse ModelProvider abstraction
        - Do not hardcode vendor logic
        - Structured MissionPlan output
        - Validate with Pydantic
        - Deterministic fallback when no provider configured
        - No API key required for default test path
        """
        # Check if we should use deterministic fallback
        # Fallback conditions: no API key configured, or provider is scaffold, or explicitly requested
        use_fallback = self._should_use_fallback()

        if use_fallback:
            plan = _generate_deterministic_plan(goal, template, mission_id)
            plan.title = title
            # Validate with Pydantic (already validated by construction, but extra check)
            try:
                validated = MissionPlan.model_validate(plan.model_dump())
                return validated
            except PydanticValidationError as e:
                raise ValueError(f"Fallback plan validation failed: {e}")

        # Try to use real provider
        try:
            provider = self._get_provider()
            if provider is None:
                # No provider, use fallback
                return _generate_deterministic_plan(goal, template, mission_id)

            # Build prompt - concise and configuration-driven
            system_prompt = self._build_system_prompt(template)
            user_prompt = self._build_user_prompt(goal, template, title)

            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
            ]

            response = await provider.chat(messages, model=settings.model_default_name, temperature=0.3)

            # Parse response - try to extract structured plan
            plan = self._parse_provider_response(response.content, mission_id, goal, template, title)

            # Validate with Pydantic
            validated = MissionPlan.model_validate(plan.model_dump() if isinstance(plan, MissionPlan) else plan)

            # Validate DAG
            dag_tasks = [{"id": t.id or t.title.lower().replace(" ", "_"), "title": t.title, "dependencies": t.dependencies} for t in validated.tasks]
            dag_result = validate_and_plan_dag(dag_tasks)
            validated.dag = MissionDAG(
                nodes=dag_result.nodes,
                edges=dag_result.edges,
                layers=dag_result.layers,
                topological_order=dag_result.topological_order,
            )

            return validated

        except Exception as e:
            # On any provider failure, fallback to deterministic plan (safe for tests)
            # Log error but don't leak secrets
            # print(f"Provider failed, using fallback: {e}")  # Avoid logging in prod, but ok for debug
            fallback = _generate_deterministic_plan(goal, template, mission_id)
            fallback.title = title
            fallback.metadata = {"fallback": True, "fallback_reason": str(e)[:200], "template": template}
            return fallback

    def _should_use_fallback(self) -> bool:
        """
        Determine if deterministic fallback should be used
        Conditions: no API key, or env indicates test/dev, or provider not configured
        """
        # Check if API keys are present
        has_openai = bool(settings.openai_api_key or settings.arena_api_key)
        has_anthropic = bool(settings.anthropic_api_key)

        # If no keys at all, use fallback (no API key required for default test path)
        if not has_openai and not has_anthropic:
            return True

        # If explicitly set to use fallback via env or feature flag
        if not settings.feature_real_llm:
            return True

        return False

    def _build_system_prompt(self, template: str) -> str:
        """Concise, configuration-driven system prompt"""
        return f"""You are Supervisor, planner & orchestrator for NexusOS.
Decompose missions into DAG, assign tasks, monitor, replan.
Template: {template}
Agent types: supervisor (planning/coordination), researcher (research/info gathering), coder (code implementation), analyst (analysis/data).
Output structured JSON matching MissionPlan schema:
{{
  "tasks": [
    {{"id": "task_id", "title": "...", "description": "...", "agent_type": "researcher|coder|analyst|supervisor", "dependencies": []}}
  ]
}}
Keep tasks concise, dependencies valid, no cycles.
No direct FS/write.
Tools: task_create, task_assign, memory_search, approval_request.
"""

    def _build_user_prompt(self, goal: str, template: str, title: Optional[str] = None) -> str:
        return f"""Mission Title: {title or 'Untitled'}
Goal: {goal}
Template: {template}

Decompose into 3-5 tasks with dependencies.
Ensure DAG is valid (no cycles, dependencies exist).
Assign appropriate agent_type per task.
Return JSON only.
"""

    def _parse_provider_response(
        self, content: str, mission_id: uuid.UUID, goal: str, template: str, title: Optional[str]
    ) -> MissionPlan:
        """
        Parse provider response, validate, fallback if invalid
        """
        import json
        import re

        # Try to extract JSON from response
        # Look for JSON block
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                # Ensure tasks exist
                if "tasks" in data and isinstance(data["tasks"], list):
                    tasks = []
                    for t in data["tasks"]:
                        # Validate required fields
                        if not isinstance(t, dict):
                            continue
                        if "title" not in t:
                            continue
                        tasks.append(
                            MissionPlanTask(
                                id=t.get("id") or t["title"].lower().replace(" ", "_"),
                                title=t["title"],
                                description=t.get("description", ""),
                                agent_type=t.get("agent_type", "researcher"),
                                dependencies=t.get("dependencies", []),
                                metadata=t.get("metadata"),
                            )
                        )

                    if tasks:
                        return MissionPlan(
                            mission_id=mission_id,
                            title=title,
                            goal=goal,
                            template=MissionTemplate(template) if template in [e.value for e in MissionTemplate] else MissionTemplate.general,
                            tasks=tasks,
                            metadata={"provider": self.model_provider_name},
                        )
            except (json.JSONDecodeError, PydanticValidationError, ValueError):
                pass

        # If parsing fails, fallback
        return _generate_deterministic_plan(goal, template, mission_id)

    async def plan_dag(self, mission_plan: MissionPlan) -> MissionDAG:
        """
        Plan DAG from MissionPlan, validate
        """
        dag_tasks = [
            {"id": t.id or t.title.lower().replace(" ", "_"), "title": t.title, "dependencies": t.dependencies}
            for t in mission_plan.tasks
        ]
        result = validate_and_plan_dag(dag_tasks)
        return MissionDAG(
            nodes=result.nodes,
            edges=result.edges,
            layers=result.layers,
            topological_order=result.topological_order,
        )

    async def assign_tasks(self, mission_plan: MissionPlan) -> Dict[str, str]:
        """
        Capability-based assignment foundation
        Returns task_id -> agent_type mapping
        """
        assignments = {}
        for task in mission_plan.tasks:
            task_id = task.id or task.title.lower().replace(" ", "_")
            # Use agent_type from plan if valid, otherwise infer
            if task.agent_type in ["supervisor", "researcher", "coder", "analyst", "custom"]:
                assignments[task_id] = task.agent_type
            else:
                # Infer from title/description
                title_lower = task.title.lower()
                desc_lower = (task.description or "").lower()
                combined = f"{title_lower} {desc_lower}"
                if any(kw in combined for kw in ["research", "gather", "collect", "find", "search"]):
                    assignments[task_id] = "researcher"
                elif any(kw in combined for kw in ["code", "implement", "develop", "program", "build"]):
                    assignments[task_id] = "coder"
                elif any(kw in combined for kw in ["analyze", "analysis", "data", "process", "visualize"]):
                    assignments[task_id] = "analyst"
                else:
                    assignments[task_id] = "supervisor"

        return assignments


# Singleton
supervisor_service = SupervisorService()
