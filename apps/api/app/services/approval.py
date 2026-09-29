"""
Approval Service - Scaffold Placeholder
Balanced policy, shell always approval (D6)
No real approval flow yet
"""


class ApprovalService:
    async def request_approval(self, mission_id: str, tool_id: str, args: dict):
        return {
            "id": "scaffold-approval-id",
            "mission_id": mission_id,
            "tool_id": tool_id,
            "status": "pending",
            "message": "Approval placeholder - balanced policy, shell always approval",
        }

    async def decide(self, approval_id: str, decision: str, comment: str = ""):
        return {
            "id": approval_id,
            "decision": decision,
            "status": "scaffold",
            "comment": comment,
        }

    async def list_pending(self, mission_id: str = None):
        return []


approval_service = ApprovalService()
