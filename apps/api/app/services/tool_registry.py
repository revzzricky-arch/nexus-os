"""
Tool Registry Service - Scaffold Placeholder
"""


class ToolRegistryService:
    """Scaffold placeholder for tool registry"""

    def __init__(self):
        self.tools = [
            {
                "id": "web_search",
                "name": "Web Search",
                "description": "Search web (placeholder)",
                "source": "builtin",
                "risk_level": "low",
                "default_permission": "auto",
            },
            {
                "id": "read_file",
                "name": "Read File",
                "description": "Read file via SandboxService (placeholder)",
                "source": "builtin",
                "risk_level": "low",
                "default_permission": "auto",
            },
            {
                "id": "write_file",
                "name": "Write File",
                "description": "Write file via SandboxService (placeholder)",
                "source": "builtin",
                "risk_level": "high",
                "default_permission": "approval_required",
            },
            {
                "id": "shell",
                "name": "Shell",
                "description": "Shell via SandboxService container isolation (placeholder, always approval)",
                "source": "builtin",
                "risk_level": "critical",
                "default_permission": "approval_required",
            },
        ]

    async def list_tools(self):
        return self.tools

    async def get_tool(self, tool_id: str):
        for t in self.tools:
            if t["id"] == tool_id:
                return t
        return None


tool_registry_service = ToolRegistryService()
