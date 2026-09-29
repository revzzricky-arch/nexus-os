# ADR 003: pgvector vs Qdrant

**Status:** Accepted
**Date:** 2026-09-29

## Context
Need vector storage for memory and RAG. Options: pgvector in Postgres vs dedicated Qdrant/Milvus.

## Decision
- MVP: Postgres + pgvector (IVFFlat, lists=100, cosine)
- Collections: memory_entries.embedding, rag_chunks.embedding
- Hybrid search: vector + tsvector keyword
- Local embedding provider first (D2), replaceable
- Keep migration path to Qdrant if >1M vectors or latency >200ms p95

## Consequences
- Single DB, simpler ops
- Good enough for <100k vectors
- Need to handle single dimension per table (configurable)
- Future migration possible

## Alternatives Rejected
- Qdrant MVP: extra infra, not needed yet
- Milvus: heavy
