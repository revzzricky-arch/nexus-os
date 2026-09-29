# ADR 011: Naming - Temporary Codename

**Status:** Accepted (v0.2 Review)
**Date:** 2026-09-29
**Decision:** D8 NEXUS temporary codename, public name TBD, D9 MIT

## Context
Multiple existing projects already use NexusOS. Need to avoid claiming final unique public brand.

## Decision
- **Internal Codename:** NEXUS / NexusOS is internal repository/project codename only, used in repo `revzzricky-arch/nexus-os`, docs, code
- **NOT Final Public Brand:** Do NOT claim NexusOS is final unique public brand. Public product name will be finalized later after trademark search and uniqueness check
- **Usage:** Code, docs, Docker Compose service names, env vars can use NEXUS codename for now, but README and marketing should note "Codename NEXUS, public name TBD"
- **License:** MIT (D9) for codename project
- **Future:** When public name finalized, rename marketing, keep codename as internal if needed

## Consequences
- Avoids trademark confusion
- Allows future rebrand without code churn
- Clear communication

## Alternatives Rejected
- Claiming NexusOS as final unique public brand: rejected per review, multiple existing projects use it
- Immediate rebrand without placeholder: confusing, codename needed for dev
