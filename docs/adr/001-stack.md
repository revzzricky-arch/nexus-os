# ADR 001: Frontend & Monorepo Stack

**Status:** Accepted (v0.2 Review)
**Date:** 2026-09-29
**Decisions:** D3 pnpm, D9 MIT, D7 Docker Compose, frontend targets

## Context
Need current stable-compatible frontend architecture without hard-pinned patch versions. Review requires Next.js 16.x, React 19, R3F 9, etc.

## Decision
- **Frontend:** Next.js 16.x (App Router) + React 19 + TypeScript + Tailwind + shadcn/ui + Zustand + TanStack Query + Three.js (current stable) + React Three Fiber 9 + Drei (current stable) + Framer Motion + Zod
- **Package Manager:** pnpm (D3) for monorepo workspaces
- **License:** MIT (D9)
- **Deployment MVP:** Docker Compose only (D7), no cloud vendor commitment
- **No hard-pinned patch versions:** Target current stable-compatible, specify major/minor range (e.g., 16.x) not patch
- **Monorepo:** pnpm workspaces + Turborepo optional, packages/shared for types

## Consequences
- Stays compatible with React 19 ecosystem
- R3F 9 supports React 19
- pnpm fast, strict
- MIT permissive
- Docker Compose avoids vendor lock-in

## Alternatives Rejected
- Next.js 14 / R3F 8 hard-pinned: outdated per review
- npm: slower, less strict than pnpm
- Hard-pinned patch versions: brittle, rejected per review
