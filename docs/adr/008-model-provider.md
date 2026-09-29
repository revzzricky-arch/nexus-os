# ADR 008: Model Provider Abstraction

**Status:** Accepted (v0.2 Review)
**Date:** 2026-09-29
**Decision:** D1 Custom lightweight ModelProvider

## Context
Need to support multiple LLM providers, including Arena/OpenAI-compatible. Avoid heavy dependency.

## Decision
- **Interface:** ModelProvider with methods:
  - chat(messages, model, tools, temperature, max_tokens) -> response
  - stream_chat(...) -> async iterator
  - cost tracking (tokens in/out, cost calc via pricing table)
- **Implementations (D1):**
  ```
  ModelProvider
   ├── OpenAICompatibleProvider (OpenAI, Groq, Together, Arena/OpenAI-compatible, any OpenAI-compatible API)
   ├── AnthropicProvider
   └── OllamaProvider (local)
  ```
- **Arena/OpenAI-compatible:** Fits behind OpenAICompatibleProvider via base_url config (e.g., Arena API endpoint), no separate provider needed
- **Config:** Pydantic Settings, env vars for keys, base_url override, model mapping
- **No heavy LiteLLM dep:** Custom ~200-line wrapper, full control, minimal deps (openai, anthropic SDKs + httpx)
- **Cost:** Tracked per call, aggregated per task/mission

## Consequences
- Lightweight, testable
- Arena fits naturally
- Easy to add new provider
- No heavy dependency

## Alternatives Rejected
- LiteLLM: heavy, extra dep, overkill for MVP, rejected per D1 selection
- Direct SDK calls everywhere: no abstraction, hard to swap
