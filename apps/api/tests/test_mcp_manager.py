"""
MCP Manager Tests - Phase 2B-4
stdio/streamable_http/SSE forbidden/mock discovery/no arbitrary auto-connect
+ SSE enforcement + secret reference validation
"""

import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.services.mcp_manager import mcp_manager, is_private_or_internal_url, is_secret_reference
from app.core.exceptions import ValidationError


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

    with pytest.raises(ValidationError) as exc:
        await mcp_manager.create_server(async_session, name="sse test", transport="sse_legacy", url="https://example.com/sse")
    assert "sse_legacy transport is disabled by default" in str(exc.value)


@pytest.mark.asyncio
async def test_sse_creating_fails_stdio_and_http_succeed(async_session: AsyncSession):
    s1 = await mcp_manager.create_server(async_session, name="ok stdio", transport="stdio", command="python -m server")
    assert s1.transport == "stdio"

    s2 = await mcp_manager.create_server(async_session, name="ok http", transport="streamable_http", url="https://example.com/mcp")
    assert s2.transport == "streamable_http"

    with pytest.raises(ValidationError):
        await mcp_manager.create_server(async_session, name="bad private", transport="streamable_http", url="http://192.168.1.1/mcp")

    with pytest.raises(ValidationError):
        await mcp_manager.create_server(async_session, name="bad sse", transport="sse_legacy", url="https://example.com/sse")


@pytest.mark.asyncio
async def test_mock_discovery(async_session: AsyncSession):
    server = await mcp_manager.create_server(async_session, name="mock test server", transport="stdio", command="python -m mock")
    tools = await mcp_manager.discover_tools(async_session, server.id)
    assert len(tools) == 1
    assert "mock" in tools[0]["name"].lower()


@pytest.mark.asyncio
async def test_no_arbitrary_auto_connect(async_session: AsyncSession):
    servers = await mcp_manager.list_servers(async_session)
    assert isinstance(servers, list)
    with pytest.raises(ValidationError):
        await mcp_manager.create_server(async_session, name="evil", transport="streamable_http", url="javascript:alert(1)")

    with pytest.raises(ValidationError):
        await mcp_manager.create_server(async_session, name="evil2", transport="streamable_http", url="ftp://example.com")


def test_is_secret_reference():
    assert is_secret_reference("${SECRET_NAME}") is True
    assert is_secret_reference("${OPENAI_API_KEY}") is True
    assert is_secret_reference("${{ secrets.MY_SECRET }}") is True
    assert is_secret_reference("${env:MY_SECRET}") is True
    assert is_secret_reference({"secret_ref": "MY_SECRET"}) is True
    assert is_secret_reference({"secretRef": "MY_SECRET"}) is True
    assert is_secret_reference("raw-secret-value") is False
    assert is_secret_reference("sk-1234567890abcdef") is False
    assert is_secret_reference("mypassword123") is False


@pytest.mark.asyncio
async def test_secret_reference_accepted(async_session: AsyncSession):
    server = await mcp_manager.create_server(
        async_session,
        name="test secret ref",
        transport="stdio",
        command="python -m server",
        env={"API_KEY": "${OPENAI_API_KEY}", "OTHER": "non-sensitive-value"},
    )
    assert server.env["API_KEY"] == "${OPENAI_API_KEY}"


@pytest.mark.asyncio
async def test_raw_api_token_rejected(async_session: AsyncSession):
    with pytest.raises(ValidationError) as exc:
        await mcp_manager.create_server(
            async_session,
            name="bad token",
            transport="stdio",
            command="python -m server",
            env={"api_key": "sk-1234567890abcdef1234567890"},
        )
    assert "Raw secret values forbidden" in str(exc.value) or "secret" in str(exc.value).lower()
    assert "sk-1234567890abcdef1234567890" not in str(exc.value)


@pytest.mark.asyncio
async def test_raw_password_rejected(async_session: AsyncSession):
    with pytest.raises(ValidationError):
        await mcp_manager.create_server(
            async_session,
            name="bad password",
            transport="stdio",
            command="python -m server",
            env={"password": "supersecretpassword123"},
        )


@pytest.mark.asyncio
async def test_response_never_exposes_secret_values(async_session: AsyncSession):
    server = await mcp_manager.create_server(
        async_session,
        name="test redact",
        transport="stdio",
        command="python -m server",
        env={"API_KEY": "${MY_SECRET}", "PUBLIC": "public-value"},
    )
    from app.routers.mcp import _redact_env
    redacted = _redact_env(server.env)
    assert redacted["API_KEY"] == "***REDACTED***"
    assert redacted["PUBLIC"] == "public-value"
    assert server.env["API_KEY"] == "${MY_SECRET}"
