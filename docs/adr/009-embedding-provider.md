# ADR 009: Embedding Provider - Local First

**Status:** Accepted (v0.2 Review)
**Date:** 2026-09-29
**Decision:** D2 Local embedding first, replaceable

## Context
Need embeddings for RAG and memory. Cost, privacy, offline support matter. Review selects local-first.

## Decision
- **Interface:** EmbeddingProvider with embed(texts: list[str]) -> list[vector]
- **MVP Implementation (D2):** Local-first
  - Option A: Ollama nomic-embed-text (768 dim) or all-minilm (384 dim)
  - Option B: SentenceTransformers bge-small-en-v1.5 (384 dim) via Python
  - Runs locally, free, no API key, privacy-preserving
  - Configurable dimension, single model for MVP
- **Replaceable:** Via config, can swap to OpenAI-compatible embedding provider later (e.g., text-embedding-3-small 1536 dim) without code change
- **Caching:** Redis cache embedding:{hash} to avoid re-embedding
- **Storage:** pgvector with dimension matching provider (configurable, migration if changed)

## Consequences
- No cost for embeddings MVP
- Works offline
- Lower quality than OpenAI large but acceptable for MVP
- Easy to replace later

## Alternatives Rejected
- OpenAI-only: cost, requires API key, rejected per D2
- Hard-pinned 1536 dim: not compatible with local 384 dim, rejected
- No abstraction: hard to swap
