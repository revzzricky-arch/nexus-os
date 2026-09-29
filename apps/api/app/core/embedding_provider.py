"""
NEXUS (Codename) - Embedding Provider Abstraction
Per review D2: Local-first, replaceable
No real embedding pipeline in scaffold
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel


class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
    provider: str
    usage: dict  # tokens, etc.


class EmbeddingProvider(ABC):
    """
    EmbeddingProvider interface - scaffold
    Local-first, replaceable
    """

    @abstractmethod
    async def embed(self, texts: List[str]) -> EmbeddingResponse:
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        pass


class LocalEmbeddingProvider(EmbeddingProvider):
    """
    Local embedding provider - scaffold stub
    D2 selected: local-first (bge-small, nomic-embed-text via Ollama, etc.)
    No real embedding in scaffold phase
    """

    def __init__(self, model: str = "bge-small-en-v1.5", dimension: int = 384):
        self.model = model
        self.dimension = dimension
        self.provider_name = "local"

    async def embed(self, texts: List[str]) -> EmbeddingResponse:
        # Scaffold: return zero vectors, no real embedding
        # In Phase 2, would use SentenceTransformers or Ollama
        fake_embeddings = [[0.0] * self.dimension for _ in texts]
        return EmbeddingResponse(
            embeddings=fake_embeddings,
            model=self.model,
            provider=self.provider_name,
            usage={"total_tokens": 0},
        )

    def get_dimension(self) -> int:
        return self.dimension

    def get_provider_name(self) -> str:
        return self.provider_name


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI-compatible embedding provider - scaffold stub
    For future replaceable use (e.g., text-embedding-3-small)
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
    ):
        self.model = model
        self.dimension = dimension
        self.api_key = api_key
        self.base_url = base_url
        self.provider_name = "openai-compatible"

    async def embed(self, texts: List[str]) -> EmbeddingResponse:
        fake_embeddings = [[0.0] * self.dimension for _ in texts]
        return EmbeddingResponse(
            embeddings=fake_embeddings,
            model=self.model,
            provider=self.provider_name,
            usage={"total_tokens": 0},
        )

    def get_dimension(self) -> int:
        return self.dimension

    def get_provider_name(self) -> str:
        return self.provider_name


def get_embedding_provider(provider_name: str = "local") -> EmbeddingProvider:
    """
    Factory for EmbeddingProvider - scaffold
    provider_name: local, openai-compatible
    D2: local first, replaceable later
    """
    from app.config import settings

    if provider_name == "local":
        return LocalEmbeddingProvider(
            model=settings.embedding_model, dimension=settings.embedding_dimension
        )
    elif provider_name == "openai-compatible":
        return OpenAICompatibleEmbeddingProvider(
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    else:
        return LocalEmbeddingProvider()
