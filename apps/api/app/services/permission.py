"""
Permission Engine - Scaffold Placeholder
Balanced policy, shell always approval (D6)
"""


class PermissionService:
    """Scaffold placeholder for permission engine"""

    async def check_permission(self, tool_id: str, agent_type: str, args: dict) -> dict:
        # Balanced policy scaffold: shell always approval
        if tool_id == "shell":
            return {
                "permission": "approval_required",
                "reason": "Shell always requires approval per D6 balanced policy",
                "requires_approval": True,
            }
        if tool_id in ("write_file",):
            return {
                "permission": "approval_required",
                "reason": "Write requires approval per balanced policy",
                "requires_approval": True,
            }
        return {
            "permission": "auto",
            "reason": "Auto allowed per balanced policy",
            "requires_approval": False,
        }


permission_service = PermissionService()
