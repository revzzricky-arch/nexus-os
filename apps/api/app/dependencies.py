"""
Dependencies - Phase 2B-2 Mission API + EventBus Foundation
Database + Authentication (D4 Bearer token)
"""

from typing import AsyncGenerator, Optional
from fastapi import Header, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
import secrets

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.core.exceptions import UnauthorizedError


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Database session dependency - async SQLAlchemy
    Yields session and handles commit/rollback
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _extract_token(authorization: Optional[str], x_nexus_token: Optional[str]) -> Optional[str]:
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "").strip()
    elif x_nexus_token:
        token = x_nexus_token.strip()
    return token


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_nexus_token: Optional[str] = Header(None, alias="X-Nexus-Token"),
):
    """
    Bearer Auth - D4 single dev token
    Preserves existing security abstraction
    Uses Authorization: Bearer <NEXUS_DEV_TOKEN> or X-Nexus-Token header
    Does NOT support ?token= in URL (security requirement)
    Never logs bearer token
    """
    token = _extract_token(authorization, x_nexus_token)

    if not token:
        raise UnauthorizedError(message="Authentication required")

    expected = settings.nexus_dev_token
    # Constant time compare to prevent timing attacks
    if not secrets.compare_digest(token, expected):
        raise UnauthorizedError(message="Invalid token")

    # MVP single-user behavior: authenticated requests may access shared dev user's data
    # Structure so per-user authorization can be strengthened later
    return {"user_id": "dev-user", "token_valid": True}


async def get_current_user_optional(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_nexus_token: Optional[str] = Header(None, alias="X-Nexus-Token"),
):
    """
    Optional auth for health/version endpoints
    """
    try:
        token = _extract_token(authorization, x_nexus_token)
        if token and secrets.compare_digest(token, settings.nexus_dev_token):
            return {"user_id": "dev-user", "token_valid": True}
    except Exception:
        pass
    return {"user_id": "anonymous", "token_valid": False}
