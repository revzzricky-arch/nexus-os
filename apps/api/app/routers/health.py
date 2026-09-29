"""
Health and Version endpoints - Scaffold
Must start successfully
"""

from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "nexus-api",
        "env": settings.env,
        "version": settings.version,
        "codename": "NEXUS",
        "note": "Temporary codename - public name TBD",
    }


@router.get("/version")
async def version():
    return {
        "service": "nexus-api",
        "version": settings.version,
        "codename": "NEXUS",
        "codename_note": "Temporary codename - public product name TBD",
        "stack": {
            "framework": "FastAPI",
            "python": "3.12",
            "deployment": "Docker Compose (MVP, D7)",
            "model_provider": "lightweight ModelProvider: openai-compatible incl Arena, anthropic, ollama (D1)",
            "embedding_provider": "local-first replaceable (D2)",
            "mcp_transport": "stdio local + streamable_http remote, sse_legacy only (per review)",
            "sandbox": "SandboxService abstraction, container isolation (no unrestricted host access)",
            "frontend_target": "Next.js 16.x + React 19 + R3F 9",
        },
        "decisions": {
            "D1": "custom lightweight ModelProvider",
            "D2": "local embedding first replaceable",
            "D3": "pnpm",
            "D4": "single dev Bearer token",
            "D5": "hybrid orbital agents + layered task DAG",
            "D6": "balanced approval, shell always approval",
            "D7": "Docker Compose first",
            "D8": "NEXUS temporary codename",
            "D9": "MIT",
            "D10": "scaffold first",
        },
        "scaffold": True,
        "limitations": "Scaffold phase - no real agents, MCP, RAG, LLM calls, approvals, tool exec",
    }
