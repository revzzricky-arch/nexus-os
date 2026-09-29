"""
PermissionService - Phase 2B-4 Real Implementation

Rules:
- forbidden -> deny
- shell ALWAYS approval (D6 balanced policy)
- critical/high -> approval_required
- low-risk read-only -> auto where allowed
- mission overrides respected
- argument-level rules deterministic
- prevent bypass ensuring AgentRunner always passes through
"""

import uuid
import re
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.models.tool import ToolRegistry, ToolPermission
from app.schemas.tool import ToolPermissionType, ToolRiskLevel
from app.core.exceptions import ValidationError


class PermissionDecisionResult:
    def __init__(
        self,
        decision: str,
        permission: str,
        reason: str,
        risk_level: str,
        evaluated_policy: Dict[str, Any],
        requires_approval: bool = False,
    ):
        self.decision = decision
        self.permission = permission
        self.reason = reason
        self.risk_level = risk_level
        self.evaluated_policy = evaluated_policy
        self.requires_approval = requires_approval

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "permission": self.permission,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "evaluated_policy": self.evaluated_policy,
            "requires_approval": self.requires_approval,
        }


class PermissionService:
    """
    Permission evaluation with deterministic rules
    """

    # Tool IDs that ALWAYS require approval per D6
    ALWAYS_APPROVAL_TOOLS = {"shell"}

    # Forbidden tools default - can be overridden by mission policy but default deny
    # Empty for MVP but extensible

    async def evaluate(
        self,
        session: AsyncSession,
        agent_type: str,
        tool_id: str,
        args: Dict[str, Any],
        mission_id: Optional[uuid.UUID] = None,
        mission_policy: Optional[Dict[str, Any]] = None,
    ) -> PermissionDecisionResult:
        """
        Evaluate permission for agent_type, tool_id, args, mission_policy
        Returns Decision allow/deny/require_approval + reason + risk_level + evaluated policy
        """

        # Fetch tool
        result = await session.execute(select(ToolRegistry).where(ToolRegistry.id == tool_id))
        tool = result.scalar_one_or_none()

        if not tool:
            return PermissionDecisionResult(
                decision="deny",
                permission="forbidden",
                reason=f"Tool {tool_id} not found in registry",
                risk_level="critical",
                evaluated_policy={"tool_id": tool_id, "found": False},
                requires_approval=False,
            )

        risk_level = tool.risk_level
        default_permission = tool.default_permission

        # Step 1: Check mission_policy overrides (if provided)
        # mission_policy can contain tool_permissions dict
        if mission_policy:
            # Example: {"tool_permissions": {"shell": "forbidden", "write_file": "auto"}}
            tool_perms = mission_policy.get("tool_permissions", {})
            if tool_id in tool_perms:
                override = tool_perms[tool_id]
                # Validate override is known permission type
                if override in ["forbidden", "approval_required", "auto", "read_only_auto"]:
                    if override == "forbidden":
                        return PermissionDecisionResult(
                            decision="deny",
                            permission="forbidden",
                            reason=f"Tool {tool_id} forbidden by mission policy override",
                            risk_level=risk_level,
                            evaluated_policy={"override": override, "source": "mission_policy"},
                            requires_approval=False,
                        )
                    elif override == "approval_required":
                        return PermissionDecisionResult(
                            decision="require_approval",
                            permission="approval_required",
                            reason=f"Tool {tool_id} requires approval by mission policy override",
                            risk_level=risk_level,
                            evaluated_policy={"override": override, "source": "mission_policy"},
                            requires_approval=True,
                        )
                    else:
                        # auto allowed, but still check always-approval rule
                        if tool_id in self.ALWAYS_APPROVAL_TOOLS:
                            return PermissionDecisionResult(
                                decision="require_approval",
                                permission="approval_required",
                                reason=f"Tool {tool_id} ALWAYS requires approval per D6 balanced policy, mission override cannot bypass",
                                risk_level=risk_level,
                                evaluated_policy={"override": override, "always_approval": True, "source": "mission_policy"},
                                requires_approval=True,
                            )
                        return PermissionDecisionResult(
                            decision="allow",
                            permission=override,
                            reason=f"Tool {tool_id} allowed by mission policy override",
                            risk_level=risk_level,
                            evaluated_policy={"override": override, "source": "mission_policy"},
                            requires_approval=False,
                        )

        # Step 2: Check DB tool_permissions for specific overrides
        # Query: tool_id match AND (agent_type match OR None) AND (mission_id match OR None)
        # Priority: mission-specific + agent-specific > mission-specific > agent-specific > global
        query = select(ToolPermission).where(ToolPermission.tool_id == tool_id)
        result = await session.execute(query)
        permissions = list(result.scalars().all())

        # Filter and sort by specificity
        # Score: mission_id match = 2, agent_type match = 1, both = 3, none = 0
        def specificity(p: ToolPermission) -> int:
            score = 0
            if p.mission_id is not None and mission_id is not None and p.mission_id == mission_id:
                score += 2
            elif p.mission_id is not None and mission_id is None:
                # Mission-specific permission but no mission_id provided -> not applicable
                return -1
            elif p.mission_id is not None and mission_id is not None and p.mission_id != mission_id:
                return -1
            # mission_id None means global
            if p.agent_type is not None and p.agent_type == agent_type:
                score += 1
            elif p.agent_type is not None and p.agent_type != agent_type:
                return -1
            return score

        applicable = []
        for p in permissions:
            s = specificity(p)
            if s >= 0:
                applicable.append((s, p))

        # Sort by specificity descending
        applicable.sort(key=lambda x: x[0], reverse=True)

        if applicable:
            # Highest specificity wins
            _, perm = applicable[0]
            # Check arg_pattern if present
            if perm.arg_pattern:
                if not self._matches_arg_pattern(args, perm.arg_pattern):
                    # Pattern doesn't match, skip this permission, try next
                    pass
                else:
                    # Pattern matches, use this permission
                    if perm.permission == "forbidden":
                        return PermissionDecisionResult(
                            decision="deny",
                            permission="forbidden",
                            reason=f"Tool {tool_id} forbidden by permission policy (agent_type={agent_type}, mission={mission_id})",
                            risk_level=risk_level,
                            evaluated_policy={"permission_id": str(perm.id), "specificity": applicable[0][0], "arg_pattern": perm.arg_pattern},
                            requires_approval=False,
                        )
                    elif perm.permission == "approval_required":
                        return PermissionDecisionResult(
                            decision="require_approval",
                            permission="approval_required",
                            reason=f"Tool {tool_id} requires approval by permission policy",
                            risk_level=risk_level,
                            evaluated_policy={"permission_id": str(perm.id), "specificity": applicable[0][0]},
                            requires_approval=True,
                        )
                    else:
                        # auto but check always approval
                        if tool_id in self.ALWAYS_APPROVAL_TOOLS:
                            return PermissionDecisionResult(
                                decision="require_approval",
                                permission="approval_required",
                                reason=f"Tool {tool_id} ALWAYS requires approval per D6, cannot be auto even via permission policy",
                                risk_level=risk_level,
                                evaluated_policy={"permission_id": str(perm.id), "always_approval": True},
                                requires_approval=True,
                            )
                        return PermissionDecisionResult(
                            decision="allow",
                            permission=perm.permission,
                            reason=f"Tool {tool_id} allowed by permission policy",
                            risk_level=risk_level,
                            evaluated_policy={"permission_id": str(perm.id), "specificity": applicable[0][0]},
                            requires_approval=False,
                        )
            else:
                # No arg pattern, use permission
                perm = applicable[0][1]
                if perm.permission == "forbidden":
                    return PermissionDecisionResult(
                        decision="deny",
                        permission="forbidden",
                        reason=f"Tool {tool_id} forbidden by permission policy",
                        risk_level=risk_level,
                        evaluated_policy={"permission_id": str(perm.id), "specificity": applicable[0][0]},
                        requires_approval=False,
                    )
                elif perm.permission == "approval_required":
                    return PermissionDecisionResult(
                        decision="require_approval",
                        permission="approval_required",
                        reason=f"Tool {tool_id} requires approval by permission policy",
                        risk_level=risk_level,
                        evaluated_policy={"permission_id": str(perm.id), "specificity": applicable[0][0]},
                        requires_approval=True,
                    )
                else:
                    if tool_id in self.ALWAYS_APPROVAL_TOOLS:
                        return PermissionDecisionResult(
                            decision="require_approval",
                            permission="approval_required",
                            reason=f"Tool {tool_id} ALWAYS requires approval per D6",
                            risk_level=risk_level,
                            evaluated_policy={"permission_id": str(perm.id), "always_approval": True},
                            requires_approval=True,
                        )
                    return PermissionDecisionResult(
                        decision="allow",
                        permission=perm.permission,
                        reason=f"Tool {tool_id} allowed by permission policy",
                        risk_level=risk_level,
                        evaluated_policy={"permission_id": str(perm.id), "specificity": applicable[0][0]},
                        requires_approval=False,
                    )

        # Step 3: Check default permission from tool registry
        # Rule: shell ALWAYS approval
        if tool_id in self.ALWAYS_APPROVAL_TOOLS:
            return PermissionDecisionResult(
                decision="require_approval",
                permission="approval_required",
                reason=f"Tool {tool_id} ALWAYS requires approval per D6 balanced policy",
                risk_level=risk_level,
                evaluated_policy={"default_permission": default_permission, "always_approval": True, "risk_level": risk_level},
                requires_approval=True,
            )

        # Rule: forbidden -> deny
        if default_permission == "forbidden":
            return PermissionDecisionResult(
                decision="deny",
                permission="forbidden",
                reason=f"Tool {tool_id} forbidden by default policy",
                risk_level=risk_level,
                evaluated_policy={"default_permission": default_permission, "risk_level": risk_level},
                requires_approval=False,
            )

        # Rule: critical/high -> approval_required
        if risk_level in ["critical", "high"]:
            return PermissionDecisionResult(
                decision="require_approval",
                permission="approval_required",
                reason=f"Tool {tool_id} risk level {risk_level} requires approval",
                risk_level=risk_level,
                evaluated_policy={"default_permission": default_permission, "risk_level": risk_level},
                requires_approval=True,
            )

        # Rule: approval_required -> require approval
        if default_permission == "approval_required":
            return PermissionDecisionResult(
                decision="require_approval",
                permission="approval_required",
                reason=f"Tool {tool_id} default permission approval_required",
                risk_level=risk_level,
                evaluated_policy={"default_permission": default_permission, "risk_level": risk_level},
                requires_approval=True,
            )

        # Rule: low-risk read-only -> auto
        if default_permission in ["auto", "read_only_auto"] and risk_level in ["low", "medium"]:
            # Additional argument-level checks for read_file etc
            # For read_file, ensure path not suspicious (though sandbox also checks)
            if tool_id == "read_file":
                path = args.get("path", "")
                if self._is_suspicious_path(path):
                    return PermissionDecisionResult(
                        decision="require_approval",
                        permission="approval_required",
                        reason=f"Tool {tool_id} suspicious path requires approval",
                        risk_level="medium",
                        evaluated_policy={"default_permission": default_permission, "risk_level": risk_level, "suspicious_path": True},
                        requires_approval=True,
                    )

            return PermissionDecisionResult(
                decision="allow",
                permission=default_permission,
                reason=f"Tool {tool_id} low-risk {risk_level} auto allowed",
                risk_level=risk_level,
                evaluated_policy={"default_permission": default_permission, "risk_level": risk_level},
                requires_approval=False,
            )

        # Fallback: require approval for safety
        return PermissionDecisionResult(
            decision="require_approval",
            permission="approval_required",
            reason=f"Tool {tool_id} fallback requires approval",
            risk_level=risk_level,
            evaluated_policy={"default_permission": default_permission, "risk_level": risk_level, "fallback": True},
            requires_approval=True,
        )

    def _matches_arg_pattern(self, args: Dict[str, Any], pattern: Dict[str, Any]) -> bool:
        """
        Check if args match pattern - deterministic
        Pattern example: {"path": "^/workspace/output/.*", "command": ".*rm.*"}
        Values are regex patterns
        """
        for key, regex_pattern in pattern.items():
            if key not in args:
                return False
            value = str(args[key])
            try:
                if not re.search(regex_pattern, value):
                    return False
            except re.error:
                # Invalid regex, treat as literal substring
                if regex_pattern not in value:
                    return False
        return True

    def _is_suspicious_path(self, path: str) -> bool:
        if not path:
            return True
        suspicious = ["..", "/etc/", "/root/", "/home/", "/var/", "/usr/", "/bin/", "/sbin/"]
        for s in suspicious:
            if s in path:
                return True
        return False


permission_service = PermissionService()
