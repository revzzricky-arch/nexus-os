"""
NEXUS (Codename) - FastAPI Application Entry Point
Scaffold Phase - Minimal API with health/version, placeholder routers
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import health, missions, tasks, agents, tools, mcp, memory, rag, approvals, ws

# Create FastAPI app
app = FastAPI(
    title="NEXUS API (Codename)",
    description="3D Agent Operating System / AI Agent Command Center - Scaffold Phase. Temporary codename NEXUS, public name TBD.",
    version=settings.version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS - allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers - health/version at root, others under /api/v1
app.include_router(health.router, tags=["system"])
app.include_router(missions.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")
app.include_router(mcp.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")
app.include_router(approvals.router, prefix="/api/v1")
app.include_router(ws.router)


@app.get("/")
async def root():
    return {
        "service": "nexus-api",
        "codename": "NEXUS",
        "codename_note": "Temporary codename - public product name TBD due to existing NexusOS projects",
        "version": settings.version,
        "env": settings.env,
        "status": "scaffold",
        "docs": "/docs",
        "health": "/health",
        "version_endpoint": "/version",
        "api_prefix": "/api/v1",
        "ws": "/ws",
        "scaffold": True,
        "limitations": "No real agents, MCP, RAG, LLM calls, approvals, tool exec - scaffold only",
        "decisions": {
            "D1": "custom lightweight ModelProvider",
            "D2": "local embedding first",
            "D3": "pnpm",
            "D4": "single Bearer token",
            "D5": "hybrid orbital+layered DAG",
            "D6": "balanced approval shell always",
            "D7": "Docker Compose first",
            "D8": "NEXUS temporary codename",
            "D9": "MIT",
            "D10": "scaffold first",
        },
    }


# For local dev
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level,
    )
