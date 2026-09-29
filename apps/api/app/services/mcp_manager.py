"""
MCP Manager - Scaffold Placeholder
Transport: stdio local, Streamable HTTP remote, SSE legacy only (per review)
No real MCP connections yet
"""

from typing import List, Dict, Any
from enum import Enum


class MCPTransport(str, Enum):
    STDIO = "stdio"  # local
    STREAMABLE_HTTP = "streamable_http"  # remote, current spec
    SSE_LEGACY = "sse_legacy"  # legacy compat only


class MCPManagerService:
    """Scaffold placeholder for MCP manager"""

    def __init__(self):
        self.servers = []

    async def list_servers(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "filesystem",
                "name": "Filesystem MCP",
                "transport": MCPTransport.STDIO,
                "status": "scaffold - no real connection",
                "enabled": True,
            },
            {
                "id": "fetch",
                "name": "Fetch MCP",
                "transport": MCPTransport.STREAMABLE_HTTP,
                "status": "scaffold - no real connection",
                "enabled": True,
            },
        ]

    async def discover_tools(self, server_id: str) -> List[Dict[str, Any]]:
        return []

    async def call_tool(self, server_id: str, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "scaffold",
            "message": f"MCP call placeholder - no real connection to {server_id}",
            "tool": tool_name,
            "args": args,
        }


mcp_manager_service = MCPManagerService()
