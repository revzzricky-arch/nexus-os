"""
MCP Manager Tests - Phase 2B-4
stdio/streamable_http/SSE forbidden/mock discovery/no arbitrary auto-connect
"""

import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.services.mcp_manager import mcp_manager, is_private_or_internal_url
from app.core.exceptions import ValidationError


@pytest.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine):
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


def test_private_url_detection():
    assert is_private_or_internal_url("http://localhost:3000") is True
    assert is_private_or_internal_url("http://127.0.0.1:8000") is True
    assert is_private_or_internal_url("http://10.0.0.1/api") is True
    assert is_private_or_internal_url("http://192.168.1.1/api") is True
    assert is_private_or_internal_url("http://169.254.1.1") is True
    assert is_private_or_internal_url("https://example.com/api") is False
    assert is_private_or_internal_url("https://api.openai.com/v1") is False


@pytest.mark.asyncio
async def test_create_stdio_server(async_session: AsyncSession):
    server = await mcp_manager.create_server(async_session, name="test stdio", transport="stdio", command="python -m mcp_server")
    assert server.transport == "stdio"
    assert server.enabled is True


@pytest.mark.asyncio
async def test_create_stdio_requires_command(async_session: AsyncSession):
    with pytest.raises(ValidationError):
        await mcp_manager.create_server(async_session, name="bad stdio", transport="stdio", command=None)


@pytest.mark.asyncio
async def test_create_http_server_valid_url(async_session: AsyncSession):
    server = await mcp_manager.create_server(async_session, name="test http", transport="streamable_http", url="https://example.com/mcp")
    assert server.transport == "streamable_http"


@pytest.mark.asyncio
async def test_create_http_private_url_forbidden(async_session: AsyncSession):
    with pytest.raises(ValidationError):
        await mcp_manager.create_server(async_session, name="private", transport="streamable_http", url="http://127.0.0.1:8000/mcp")

    with pytest.raises(ValidationError):
        await mcp_manager.create_server(async_session, name="private2", transport="streamable_http", url="http://10.0.0.1/mcp")


@pytest.mark.asyncio
async def test_sse_forbidden_by_default(async_session: AsyncSession):
    allowed = await mcp_manager.validate_transport_allowed("sse_legacy")
    assert allowed is False

    allowed_stdio = await mcp_manager.validate_transport_allowed("stdio")
    assert allowed_stdio is True

    allowed_http = await mcp_manager.validate_transport_allowed("streamable_http")
    assert allowed_http is True


@pytest.mark.asyncio
async def test_mock_discovery(async_session: AsyncSession):
    server = await mcp_manager.create_server(async_session, name="mock test server", transport="stdio", command="python -m mock")
    tools = await mcp_manager.discover_tools(async_session, server.id)
    assert len(tools) == 1
    assert "mock" in tools[0]["name"].lower()


@pytest.mark.asyncio
async def test_no_arbitrary_auto_connect(async_session: AsyncSession):
    # list servers should not auto-connect to arbitrary URLs
    servers = await mcp_manager.list_servers(async_session)
    assert isinstance(servers, list)
    # Creating server requires explicit config, not auto-connect from prompt
    # Ensure we can't create with arbitrary URL from prompt without validation
    with pytest.raises(ValidationError):
        await mcp_manager.create_server(async_session, name="evil", transport="streamable_http", url="javascript:alert(1)")

    with pytest.raises(ValidationError):
        await mcp_manager.create_server(async_session, name="evil2", transport="streamable_http", url="ftp://example.com")
