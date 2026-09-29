# ADR 010: Deployment - Docker Compose First

**Status:** Accepted (v0.2 Review)
**Date:** 2026-09-29
**Decision:** D7 Docker Compose first, no vendor commitment, K8s future

## Context
Need MVP deployment that is simple, no vendor lock-in. Review says MVP is Docker Compose, do not commit to Fly.io, Hetzner, Vercel/Render yet, K8s future.

## Decision
- **MVP Deployment Target:** Docker Compose only (D7)
  - Services: web (Next.js 16.x standalone), api (FastAPI), postgres+pgvector, redis, sandbox-runner (for SandboxService exec), otel-collector optional
  - No commitment to specific cloud provider (Fly.io, Hetzner, Vercel, Render, etc.) yet
  - Runs on any Docker host: local, VM, etc.
  - .env file for secrets, volumes for data
  - Healthchecks, Caddyfile optional for TLS
- **Future Option:** Kubernetes remains future deployment option, not MVP
  - Potential: API replicas, HPA, managed Postgres/Redis, separate worker, Ingress
  - No decision yet
- **CI:** GitHub Actions builds images, no vendor-specific deploy hooks yet
- **Cost:** Single Compose stack handles 10 concurrent missions, local embedding saves cost

## Consequences
- Simplest MVP, no vendor lock-in
- Easy local dev parity
- No managed infra benefits yet, but acceptable for MVP
- Clear future path to K8s

## Alternatives Rejected
- Fly.io/Hetzner/Vercel/Render commitment for MVP: rejected per review, no commitment yet
- K8s for MVP: heavy, rejected as future option only
- Serverless: not suitable for long-running agents
