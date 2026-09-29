# ADR 012: Auth - Single Dev Bearer Token

**Status:** Accepted (v0.2 Review)
**Date:** 2026-09-29
**Decision:** D4 Single development Bearer token

## Context
Need auth for MVP without building full user management.

## Decision
- **MVP Auth (D4):** Single development Bearer token
  - Token stored in .env (e.g., NEXUS_DEV_TOKEN)
  - FastAPI middleware checks Authorization: Bearer <token>
  - WS token via ?token= query param, validated on connect
  - httpOnly cookie optional for web
  - No login UI, no JWT, no orgs for MVP
  - All missions owned by single dev user
- **Future:** JWT with short expiry, refresh token, orgs, RBAC (viewer, operator, admin), SSO
- **Security:** Token never logged, rate limiting per token, no secrets in events

## Consequences
- Fastest to ship
- Sufficient for single-user MVP
- No multi-tenant yet
- Clear future path

## Alternatives Rejected
- Email/password + JWT for MVP: adds 1-2 days, rejected per D4 selection
- No auth: insecure, rejected
- Full RBAC MVP: heavy, future
