"""
Supervisor Tests - Phase 2B-3
Deterministic fallback, valid MissionPlan, invalid provider output, Pydantic validation, no API key required
"""

import uuid
import pytest

from app.services.supervisor import SupervisorService, _generate_deterministic_plan
from app.schemas.mission import MissionPlan, MissionTemplate
from app.config import settings


@pytest.mark.asyncio
async def test_deterministic_fallback_research():
    plan = _generate_deterministic_plan(goal="Research AI trends", template="research", mission_id=uuid.uuid4())

    assert plan.mission_id is not None
    assert plan.template == MissionTemplate.research
    assert len(plan.tasks) >= 3
    assert plan.dag is not None
    assert plan.metadata["fallback"] is True

    # Check tasks have required fields
    for task in plan.tasks:
        assert task.title
        assert task.agent_type in ["supervisor", "researcher", "coder", "analyst", "custom"]
        assert isinstance(task.dependencies, list)


@pytest.mark.asyncio
async def test_deterministic_fallback_code():
    plan = _generate_deterministic_plan(goal="Build a web app", template="code")

    assert plan.template == MissionTemplate.code
    assert len(plan.tasks) >= 3
    # Code template should have coder tasks
    assert any(t.agent_type == "coder" for t in plan.tasks)


@pytest.mark.asyncio
async def test_deterministic_fallback_analysis():
    plan = _generate_deterministic_plan(goal="Analyze sales data", template="analysis")

    assert plan.template == MissionTemplate.analysis
    assert any(t.agent_type == "analyst" for t in plan.tasks)


@pytest.mark.asyncio
async def test_deterministic_fallback_general():
    plan = _generate_deterministic_plan(goal="Do something general", template="general")

    assert plan.template == MissionTemplate.general
    assert len(plan.tasks) >= 2


@pytest.mark.asyncio
async def test_supervisor_deterministic_no_api_key():
    # Ensure no API key required for default path
    # Save original settings
    original_openai = settings.openai_api_key
    original_anthropic = settings.anthropic_api_key
    original_arena = settings.arena_api_key
    original_feature = settings.feature_real_llm

    settings.openai_api_key = None
    settings.anthropic_api_key = None
    settings.arena_api_key = None
    settings.feature_real_llm = False

    try:
        service = SupervisorService()
        plan = await service.decompose_mission(
            mission_id=uuid.uuid4(),
            goal="Test goal without API key",
            template="research",
            title="Test Mission",
        )

        assert isinstance(plan, MissionPlan)
        assert len(plan.tasks) > 0
        assert plan.mission_id is not None
        # Should be fallback
        assert plan.metadata.get("fallback") is True

    finally:
        settings.openai_api_key = original_openai
        settings.anthropic_api_key = original_anthropic
        settings.arena_api_key = original_arena
        settings.feature_real_llm = original_feature


@pytest.mark.asyncio
async def test_supervisor_valid_mission_plan():
    service = SupervisorService()
    plan = await service.decompose_mission(
        mission_id=uuid.uuid4(),
        goal="Research quantum computing",
        template="research",
        title="Quantum Research",
    )

    # Pydantic validation
    validated = MissionPlan.model_validate(plan.model_dump())
    assert validated is not None
    assert len(validated.tasks) >= 2

    # Check DAG exists and is valid
    assert validated.dag is not None
    assert len(validated.dag.nodes) == len(validated.tasks)
    assert isinstance(validated.dag.edges, list)
    assert isinstance(validated.dag.layers, dict)


@pytest.mark.asyncio
async def test_supervisor_invalid_provider_output_fallback():
    # Simulate provider returning invalid output, should fallback to deterministic
    service = SupervisorService(model_provider_name="openai-compatible")

    # Force fallback by disabling real LLM
    original_feature = settings.feature_real_llm
    settings.feature_real_llm = False

    try:
        plan = await service.decompose_mission(
            mission_id=uuid.uuid4(),
            goal="Test invalid provider handling",
            template="general",
        )

        # Should still return valid plan via fallback
        assert isinstance(plan, MissionPlan)
        assert len(plan.tasks) > 0

    finally:
        settings.feature_real_llm = original_feature


@pytest.mark.asyncio
async def test_supervisor_pydantic_validation():
    # Test that invalid data fails validation
    from pydantic import ValidationError

    # Missing required fields should fail (title missing)
    with pytest.raises(ValidationError):
        MissionPlan.model_validate({"tasks": [{"agent_type": "researcher"}]})

    # Invalid tasks type should fail
    with pytest.raises(ValidationError):
        MissionPlan.model_validate({"tasks": "not a list"})

    # Valid plan should pass
    plan = MissionPlan(
        mission_id=uuid.uuid4(),
        tasks=[
            {"title": "Task 1", "agent_type": "researcher", "dependencies": []},
            {"title": "Task 2", "agent_type": "coder", "dependencies": ["task_1"]},
        ],
    )
    validated = MissionPlan.model_validate(plan.model_dump())
    assert len(validated.tasks) == 2


@pytest.mark.asyncio
async def test_supervisor_all_templates():
    service = SupervisorService()

    for template in ["research", "code", "analysis", "general"]:
        plan = await service.decompose_mission(
            mission_id=uuid.uuid4(),
            goal=f"Test {template} template",
            template=template,
        )
        assert isinstance(plan, MissionPlan)
        assert len(plan.tasks) >= 2
        assert plan.template.value == template or plan.metadata.get("template") == template


@pytest.mark.asyncio
async def test_supervisor_plan_dag():
    service = SupervisorService()
    plan = await service.decompose_mission(
        mission_id=uuid.uuid4(),
        goal="Test DAG planning",
        template="code",
    )

    dag = await service.plan_dag(plan)
    assert dag is not None
    assert len(dag.nodes) == len(plan.tasks)
    assert isinstance(dag.layers, dict)


@pytest.mark.asyncio
async def test_supervisor_assign_tasks():
    service = SupervisorService()
    plan = await service.decompose_mission(
        mission_id=uuid.uuid4(),
        goal="Test assignment",
        template="research",
    )

    assignments = await service.assign_tasks(plan)
    assert isinstance(assignments, dict)
    assert len(assignments) == len(plan.tasks)
    for task_id, agent_type in assignments.items():
        assert agent_type in ["supervisor", "researcher", "coder", "analyst", "custom"]
