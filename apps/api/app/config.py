"""
NEXUS (Codename) - Configuration Layer
Pydantic Settings, scaffold phase
No real LLM/MCP/RAG calls yet, only placeholders
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    # Core
    env: str = Field(default="development", alias="ENV")
    secret_key: str = Field(default="dev-secret-change-me", alias="SECRET_KEY")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # Auth - Development Bearer token, NEVER in URL query
    # For WS: use initial auth message after connection, not ?token=SECRET
    nexus_dev_token: str = Field(default="dev-token-change-me", alias="NEXUS_DEV_TOKEN")
    auth_mode: str = Field(default="bearer_token", alias="AUTH_MODE")
    auth_token_header: str = Field(default="X-Nexus-Token", alias="AUTH_TOKEN_HEADER")

    # Database - placeholders, no full schema yet
    database_url: str = Field(
        default="postgresql+asyncpg://nexus:nexus@localhost:5432/nexus",
        alias="DATABASE_URL",
    )
    postgres_user: str = Field(default="nexus", alias="POSTGRES_USER")
    postgres_password: str = Field(default="nexus", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="nexus", alias="POSTGRES_DB")

    # Redis - placeholder, no real event bus yet
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Model Provider - placeholders, no real calls in scaffold
    model_default_provider: str = Field(
        default="openai-compatible", alias="MODEL_DEFAULT_PROVIDER"
    )
    model_default_name: str = Field(default="gpt-4o-mini", alias="MODEL_DEFAULT_NAME")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    arena_api_key: Optional[str] = Field(default=None, alias="ARENA_API_KEY")
    arena_base_url: Optional[str] = Field(default=None, alias="ARENA_BASE_URL")

    # Embedding Provider - local-first, replaceable (D2)
    embedding_provider: str = Field(default="local", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="bge-small-en-v1.5", alias="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=384, alias="EMBEDDING_DIMENSION")

    # MCP - scaffold, no real connections, transport terminology per review
    mcp_filesystem_enabled: bool = Field(default=True, alias="MCP_FILESYSTEM_ENABLED")
    mcp_filesystem_transport: str = Field(default="stdio", alias="MCP_FILESYSTEM_TRANSPORT")
    mcp_fetch_enabled: bool = Field(default=True, alias="MCP_FETCH_ENABLED")
    mcp_fetch_transport: str = Field(default="streamable_http", alias="MCP_FETCH_TRANSPORT")
    mcp_fetch_url: str = Field(
        default="http://localhost:3001/mcp", alias="MCP_FETCH_URL"
    )

    # SandboxService - placeholder, no exec yet
    sandbox_service_type: str = Field(default="placeholder", alias="SANDBOX_SERVICE_TYPE")
    sandbox_workspace_root: str = Field(
        default="/tmp/nexus-workspaces", alias="SANDBOX_WORKSPACE_ROOT"
    )
    sandbox_container_runtime: str = Field(default="docker", alias="SANDBOX_CONTAINER_RUNTIME")
    sandbox_timeout_seconds: int = Field(default=30, alias="SANDBOX_TIMEOUT_SECONDS")

    # Feature flags - scaffold
    feature_mcp: bool = Field(default=False, alias="FEATURE_MCP")
    feature_rag: bool = Field(default=False, alias="FEATURE_RAG")
    feature_real_llm: bool = Field(default=False, alias="FEATURE_REAL_LLM")

    # Observability - scaffold
    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
        "protected_namespaces": ("settings_",),
    }

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.env.lower() in ("development", "dev", "local")

    @property
    def version(self) -> str:
        return "0.1.0-scaffold"


# Singleton settings
settings = Settings()

# Security: Validate no hardcoded secrets in source
# All secrets must come from env, not hardcoded
def validate_no_hardcoded_secrets():
    """
    Scaffold validation: ensure no hardcoded API keys in source
    This is placeholder, real validation in CI
    """
    # In scaffold, we just ensure settings are from env
    # Real secrets should never be in code
    pass
