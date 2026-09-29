"""
NEXUS (Codename) - Security & Auth Scaffold
Per review: Do NOT use ?token=SECRET for WS auth
Chosen approach: Initial auth message after WS connection, not URL query
"""

from fastapi import Header, HTTPException, Depends, Request
from typing import Optional
from app.config import settings
import secrets


class SecurityService:
    """
    Scaffold security service - placeholder interfaces only
    No real auth UI, no user accounts, no multi-tenancy, no RBAC yet (per scaffold limits)
    """

    @staticmethod
    def validate_bearer_token(
        authorization: Optional[str] = Header(None),
        x_nexus_token: Optional[str] = Header(None, alias="X-Nexus-Token"),
    ) -> bool:
        """
        Validate Bearer token from header
        Supports:
        - Authorization: Bearer <token>
        - X-Nexus-Token: <token> (custom header, avoids URL)
        Does NOT support ?token= in URL (per security requirement)
        """
        token = None

        if authorization and authorization.startswith("Bearer "):
            token = authorization.replace("Bearer ", "").strip()
        elif x_nexus_token:
            token = x_nexus_token.strip()

        if not token:
            # In scaffold, allow without token for /health, /version
            # For protected routes, would raise 401
            return False

        # Constant time comparison to prevent timing attacks
        expected = settings.nexus_dev_token
        if not secrets.compare_digest(token, expected):
            raise HTTPException(status_code=401, detail="Invalid token")

        return True

    @staticmethod
    def get_token_from_request(request: Request) -> Optional[str]:
        """
        Extract token from request - NEVER from query param ?token=
        Per security requirement: Do NOT use ?token=SECRET
        """
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.replace("Bearer ", "").strip()

        # Check custom header
        custom_header = request.headers.get(settings.auth_token_header)
        if custom_header:
            return custom_header.strip()

        # For WS: token should be sent as first message {type: "auth", token: "..."}
        # NOT via query param - document this approach
        # In scaffold, we don't enforce for /health, /version
        return None

    @staticmethod
    def validate_no_secrets_in_payload(payload: dict) -> dict:
        """
        Placeholder: Scan payload for secret patterns and redact
        In real implementation: regex for sk-, ghp_, AKIA, etc.
        """
        # Scaffold: no-op, just return
        return payload


# Dependency for protected routes (placeholder - not enforced in scaffold for /health, /version)
def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    x_nexus_token: Optional[str] = Header(None, alias="X-Nexus-Token"),
):
    """
    Optional auth - for scaffold, allows unauthenticated for health/version
    For future protected routes, would require valid token
    """
    try:
        if authorization or x_nexus_token:
            SecurityService.validate_bearer_token(authorization, x_nexus_token)
            return {"user_id": "dev-user", "token_valid": True}
    except HTTPException:
        # In scaffold, don't block
        pass
    return {"user_id": "anonymous", "token_valid": False}


def require_auth(
    authorization: Optional[str] = Header(None),
    x_nexus_token: Optional[str] = Header(None, alias="X-Nexus-Token"),
):
    """
    Require auth - for future protected routes
    Not used in scaffold for /health, /version
    """
    token_valid = SecurityService.validate_bearer_token(authorization, x_nexus_token)
    if not token_valid:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {"user_id": "dev-user"}


# WS Auth Approach Documentation
"""
Chosen WS Authentication Approach (Scaffold):

Per security requirement: Do NOT use ?token=SECRET in URL query param.

Selected Approach: Initial Auth Message

1. Client connects to WS without token in URL:
   ws://localhost:8000/ws (no query param)

2. Client immediately sends first message:
   {
     "type": "auth",
     "token": "Bearer <dev-token>"  # or just token value
   }

3. Server validates token via constant-time compare against NEXUS_DEV_TOKEN env
   - If valid: server responds {"type": "authenticated"} and allows subscriptions
   - If invalid: server closes connection with 4401

4. Subsequent messages use channel subscriptions, no token in URL

Alternative for browser prototype (future):
- httpOnly secure cookie set via /auth/login (not implemented in scaffold)
- Cookie automatically sent with WS upgrade, no URL token

Why not ?token=SECRET:
- URLs logged in server logs, browser history, proxies
- Token leakage via Referer header
- Violates OWASP

For scaffold, WS is placeholder only, no real streaming yet.
See docs/architecture.md §27 and packages/shared/src/events.ts WSAuthMessage
"""
