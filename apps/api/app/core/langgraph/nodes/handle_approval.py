"""
Handle Approval Node - Phase 2B-4 ApprovalRuntimeBoundary

Phase 2B-4: Implements approval interrupt handling with documented boundary for future resume
- execute_task → permission check → approval interrupt → later resume
- handle_approval/evaluate_task/replan may remain placeholders but with real approval integration
- ApprovalRuntimeBoundary isolates approval waiting from graph execution for next phase

Flow:
- If state has pending approvals, pause and wait (via ApprovalService)
- If approval decided, resume execution via handle_approval_decision
- For Phase 2B-4, we implement interface but do NOT redesign graph yet
- Future: LangGraph interrupt/resume will be used
"""

from typing import Dict, Any

from app.core.langgraph.state import MissionState


class ApprovalRuntimeBoundary:
    """
    Boundary for approval handling - isolates approval waiting logic
    Documented for next phase resume implementation

    Phase 2B-4: Provides interface for approval handling without redesigning graph
    - check_pending_approvals: check if mission has pending approvals
    - handle_decision: process approval decision and resume
    - Future: will integrate with LangGraph interrupts (Human-in-the-loop)
    """

    @staticmethod
    def is_approval_required(state: MissionState) -> bool:
        """Check if state indicates approval required"""
        return state.get("status") == "awaiting_approval" or bool(state.get("pending_approvals"))

    @staticmethod
    def get_pending_approvals(state: MissionState) -> list:
        return state.get("pending_approvals", [])

    @staticmethod
    def should_resume(state: MissionState) -> bool:
        """Check if approvals resolved and should resume execution"""
        pending = state.get("pending_approvals", [])
        if not pending:
            return True
        # If all approvals decided, resume
        return all(a.get("status") != "pending" for a in pending)


async def handle_approval_node(state: MissionState) -> Dict[str, Any]:
    """
    Handle approval - Phase 2B-4 implementation with boundary

    For Phase 2B-4:
    - Checks pending approvals in state
    - If pending, sets status to awaiting_approval
    - If approved, resumes execution
    - Emits approval_requested/decided events via boundary (handled in orchestrator)
    - Does NOT redesign main graph, but provides clean interface for next phase

    Future Phase: Will use LangGraph interrupts:
    ```
    from langgraph.types import interrupt
    decision = interrupt({"approval_id": ..., "tool": ...})
    ```
    """

    pending = state.get("pending_approvals", [])
    messages = state.get("messages", [])

    if not pending:
        return {
            "next_action": "execute_task",
            "messages": messages + [{"role": "system", "content": "Handle approval: no pending approvals, resuming execution"}],
            "approval_boundary": "ApprovalRuntimeBoundary - no pending",
        }

    # Check if approvals are pending
    has_pending = any(a.get("status") == "pending" for a in pending)

    if has_pending:
        return {
            "status": "awaiting_approval",
            "next_action": "awaiting_approval",
            "messages": messages
            + [
                {
                    "role": "system",
                    "content": f"Handle approval: {len(pending)} pending approvals, awaiting decision. Boundary: ApprovalRuntimeBoundary isolates waiting.",
                }
            ],
            "approval_boundary": "ApprovalRuntimeBoundary - awaiting approval, future interrupt/resume",
            "pending_approvals": pending,
        }

    # All approvals decided
    return {
        "next_action": "execute_task",
        "messages": messages
        + [
            {
                "role": "system",
                "content": f"Handle approval: all {len(pending)} approvals decided, resuming execution",
            }
        ],
        "approval_boundary": "ApprovalRuntimeBoundary - resumed after approvals",
        "pending_approvals": pending,
    }
