"""
MCP router - Phase 2B-4 Real Implementation with SSE forbidden + secret reference enforcement
GET /api/v1/mcp-servers, POST /mcp-servers, GET /mcp-servers/{id}/tools, DELETE /mcp-servers/{id}

Security: Do not return raw MCP env/secret values to clients, redact sensitive env fields
"""

import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, Body, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.services.mcp_manager import mcp_manager
from app.services.tool_registry import tool_registry_service
from app.schemas.tool import MCPServerCreate
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/mcp-servers", tags=["mcp"])


def _redact_env(env: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not env:
        return env
    redacted = {}
    for k, v in env.items():
        lower_k = k.lower()
        if any(secret_key in lower_k for secret_key in ["secret", "password", "token", "api_key", "apikey", "credential", "auth", "key"]):
            redacted[k] = "***REDACTED***"
        else:
            if isinstance(v, str) and len(v) > 20 and any(c in v for c in ["sk-", "secret"]):
                redacted[k] = "***REDACTED***"
            else:
                redacted[k] = v
    return redacted


def _redact_server_response(server) -> Dict[str, Any]:
    return {
        "id": str(server.id),
        "name": server.name,
        "transport": server.transport,
        "command": server.command,
        "url": server.url,
        "env": _redact_env(server.env),
        "env_redacted": True if server.env else False,
        "enabled": server.enabled,
        "status": server.status,
        "last_seen": server.last_seen.isoformat() if server.last_seen else None,
        "created_at": server.created_at.isoformat() if server.created_at else None,
        "updated_at": server.updated_at.isoformat() if server.updated_at else None,
    }


@router.get("", response_model=dict)
async def list_mcp_servers(
    enabled_only: bool = Query(False, description="Filter enabled only"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    servers = await mcp_manager.list_servers(session, enabled_only=enabled_only)
    data = [_redact_server_response(s) for s in servers]
    return {"data": data, "total": len(data)}


@router.post("", response_model=dict)
async def create_mcp_server(
    body: MCPServerCreate = Body(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        server = await mcp_manager.create_server(
            session,
            name=body.name,
            transport=body.transport.value,
            command=body.command,
            url=body.url,
            env=body.env,
            enabled=body.enabled,
        )
        return {"data": _redact_server_response(server)}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"error": {"code": "validation_error", "message": str(e), "details": e.details}})


@router.get("/{server_id}/tools", response_model=dict)
async def list_mcp_server_tools(
    server_id: uuid.UUID = Path(..., description="MCP Server ID"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        discovered = await mcp_manager.discover_tools(session, server_id)
        registered = await tool_registry_service.discover_mcp_tools(session, server_id, discovered)

        data = []
        for t in registered:
            data.append(
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "source": t.source,
                    "mcp_server_id": str(t.mcp_server_id) if t.mcp_server_id else None,
                    "risk_level": t.risk_level,
                    "default_permission": t.default_permission,
                }
            )

        return {"data": data, "total": len(data), "discovered": len(discovered)}

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": str(e)}})
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"error": {"code": "validation_error", "message": str(e)}})


@router.delete("/{server_id}", response_model=dict)
async def delete_mcp_server(
    server_id: uuid.UUID = Path(..., description="MCP Server ID"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        await mcp_manager.delete_server(session, server_id)
        return {"data": {"id": str(server_id), "deleted": True}}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": str(e)}})
