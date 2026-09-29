"""
Tool Registry Tests - Phase 2B-4
registration/lookup/listing/schema validation/seed idempotency
"""

import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.services.tool_registry import tool_registry_service, BUILTIN_TOOLS


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
async def test_seed_builtin_tools_idempotent(async_session: AsyncSession):
    tools1 = await tool_registry_service.seed_builtin_tools(async_session)
    assert len(tools1) == 6
    ids1 = {t.id for t in tools1}
    assert "web_search" in ids1
    assert "read_file" in ids1
    assert "write_file" in ids1
    assert "shell" in ids1
    assert "memory_search" in ids1
    assert "rag_query" in ids1

    tools2 = await tool_registry_service.seed_builtin_tools(async_session)
    assert len(tools2) == 6
    ids2 = {t.id for t in tools2}
    assert ids1 == ids2


@pytest.mark.asyncio
async def test_register_get_list_tools(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)

    # get existing
    tool = await tool_registry_service.get_tool(async_session, "web_search")
    assert tool is not None
    assert tool.name == "Web Search"
    assert tool.risk_level == "low"

    # list
    all_tools = await tool_registry_service.list_tools(async_session)
    assert len(all_tools) >= 6

    builtin = await tool_registry_service.list_tools(async_session, source="builtin")
    assert len(builtin) >= 6

    # register custom
    custom_def = {
        "id": "custom_tool",
        "name": "Custom",
        "description": "Custom tool",
        "source": "builtin",
        "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
        "output_schema": {"type": "object"},
        "capability_tags": ["custom"],
        "risk_level": "low",
        "default_permission": "auto",
    }
    custom = await tool_registry_service.register_tool(async_session, custom_def)
    assert custom.id == "custom_tool"

    fetched = await tool_registry_service.get_tool(async_session, "custom_tool")
    assert fetched is not None


@pytest.mark.asyncio
async def test_validate_tool_arguments(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)

    # valid
    valid_args = {"query": "test", "limit": 5}
    validated = await tool_registry_service.validate_tool_arguments(async_session, "web_search", valid_args)
    assert validated["query"] == "test"

    # invalid missing required
    from app.core.exceptions import ValidationError
    with pytest.raises(ValidationError):
        await tool_registry_service.validate_tool_arguments(async_session, "web_search", {"limit": 5})

    # invalid tool
    with pytest.raises(ValidationError):
        await tool_registry_service.validate_tool_arguments(async_session, "nonexistent", {})

    # too large args
    large_args = {"query": "x" * 20000}
    with pytest.raises(ValidationError):
        await tool_registry_service.validate_tool_arguments(async_session, "web_search", large_args)


@pytest.mark.asyncio
async def test_discover_mcp_tools(async_session: AsyncSession):
    await tool_registry_service.seed_builtin_tools(async_session)
    server_id = uuid.uuid4()
    discovered = [
        {
            "id": "mcp_test_tool",
            "name": "MCP Test Tool",
            "description": "Discovered",
            "input_schema": {"type": "object", "properties": {"input": {"type": "string"}}, "required": ["input"]},
            "output_schema": {"type": "object"},
            "capability_tags": ["mcp"],
        }
    ]
    registered = await tool_registry_service.discover_mcp_tools(async_session, server_id, discovered)
    assert len(registered) == 1
    assert registered[0].id == "mcp_test_tool"
    assert registered[0].source == "mcp"
    assert registered[0].mcp_server_id == server_id
    assert registered[0].risk_level == "medium"
    assert registered[0].default_permission == "approval_required"
