"""
Seed Tests - PR 2B-1
Test seed/bootstrap support for foundational data (agents registry)
"""

import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.db.base import Base
from app.models.agent import Agent
from app.db.seed import seed_agents, AGENT_SEEDS


@pytest.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    try:
        await engine.dispose()
    except Exception:
        pass


@pytest.fixture
async def async_session(async_engine):
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.mark.asyncio
async def test_agent_seeds_defined():
    """Agent seeds should have 4 types: supervisor, researcher, coder, analyst"""
    types = {s["type"] for s in AGENT_SEEDS}
    expected = {"supervisor", "researcher", "coder", "analyst"}
    assert types == expected, f"Expected {expected}, got {types}"
    
    for seed in AGENT_SEEDS:
        assert "role" in seed
        assert "system_prompt_template" in seed
        assert "model_config" in seed
        assert "tools" in seed
        assert "capability_tags" in seed
        # Capability/configuration driven, not large personalities
        assert len(seed["system_prompt_template"]) < 1000, "Prompt should be concise config-driven, not large personality"


@pytest.mark.asyncio
async def test_seed_agents_idempotent(async_session):
    """seed_agents should be idempotent"""
    # First seed
    agents1 = await seed_agents(async_session)
    await async_session.commit()
    assert len(agents1) == 4

    # Second seed should not duplicate
    agents2 = await seed_agents(async_session)
    await async_session.commit()
    assert len(agents2) == 4

    # Check DB count
    result = await async_session.execute(select(Agent))
    all_agents = result.scalars().all()
    assert len(all_agents) == 4, f"Expected 4 agents after idempotent seed, got {len(all_agents)}"


@pytest.mark.asyncio
async def test_seed_agents_have_correct_types(async_session):
    """Seeded agents should have correct types and roles"""
    await seed_agents(async_session)
    await async_session.commit()

    result = await async_session.execute(select(Agent))
    agents = result.scalars().all()
    
    agent_map = {a.type: a for a in agents}
    
    assert "supervisor" in agent_map
    assert agent_map["supervisor"].role == "Mission Planner & Orchestrator"
    assert "planning" in agent_map["supervisor"].capability_tags

    assert "researcher" in agent_map
    assert "coder" in agent_map
    assert "analyst" in agent_map

    # Check model_config has provider
    for agent in agents:
        assert "provider" in agent.model_config
        assert agent.model_config["provider"] in ("openai-compatible", "anthropic", "ollama")
