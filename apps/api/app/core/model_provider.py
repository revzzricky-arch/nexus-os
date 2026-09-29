"""
NEXUS (Codename) - Model Provider Abstraction
Per review D1: Custom lightweight interface
OpenAI-compatible (incl Arena), Anthropic, Ollama
No real API calls in scaffold phase
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    model: str
    provider: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    cost_cents: int = 0
    finish_reason: str = "stop"


class ModelProvider(ABC):
    """
    Lightweight ModelProvider interface - scaffold placeholder
    No real API calls yet
    """

    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ChatResponse:
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[str]:
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        pass


class OpenAICompatibleProvider(ModelProvider):
    """
    OpenAI-compatible provider - covers OpenAI, Groq, Together, Arena, etc.
    Via base_url override, Arena/OpenAI-compatible fits here
    Scaffold: stub, no real calls
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.provider_name = "openai-compatible"

    async def chat(self, messages, model, temperature=0.7, max_tokens=None, tools=None) -> ChatResponse:
        # Scaffold: return placeholder, no real API call
        return ChatResponse(
            id="scaffold-placeholder",
            model=model,
            provider=self.provider_name,
            content="[Scaffold] ModelProvider placeholder - no real LLM call yet. Configure real provider in Phase 2.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            cost_cents=0,
            finish_reason="stop",
        )

    async def stream_chat(self, messages, model, temperature=0.7, max_tokens=None, tools=None):
        # Scaffold: yield placeholder
        yield "[Scaffold] Streaming placeholder - no real LLM call yet"
        return

    def get_provider_name(self) -> str:
        return self.provider_name


class AnthropicProvider(ModelProvider):
    """Anthropic provider - scaffold stub"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.provider_name = "anthropic"

    async def chat(self, messages, model, temperature=0.7, max_tokens=None, tools=None) -> ChatResponse:
        return ChatResponse(
            id="scaffold-placeholder",
            model=model,
            provider=self.provider_name,
            content="[Scaffold] AnthropicProvider placeholder - no real call yet",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            cost_cents=0,
        )

    async def stream_chat(self, messages, model, temperature=0.7, max_tokens=None, tools=None):
        yield "[Scaffold] Anthropic streaming placeholder"
        return

    def get_provider_name(self) -> str:
        return self.provider_name


class OllamaProvider(ModelProvider):
    """Ollama provider - local - scaffold stub"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.provider_name = "ollama"

    async def chat(self, messages, model, temperature=0.7, max_tokens=None, tools=None) -> ChatResponse:
        return ChatResponse(
            id="scaffold-placeholder",
            model=model,
            provider=self.provider_name,
            content="[Scaffold] OllamaProvider placeholder - no real call yet. Run ollama serve locally for Phase 2.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            cost_cents=0,
        )

    async def stream_chat(self, messages, model, temperature=0.7, max_tokens=None, tools=None):
        yield "[Scaffold] Ollama streaming placeholder"
        return

    def get_provider_name(self) -> str:
        return self.provider_name


class DeterministicProvider(ModelProvider):
    """Deterministic provider for tests/dev - no API key required, returns valid structured output"""

    def __init__(self):
        self.provider_name = "deterministic"

    async def chat(self, messages, model, temperature=0.7, max_tokens=None, tools=None) -> ChatResponse:
        import json

        plan = {
            "tasks": [
                {"id": "task_1", "title": "Research Task", "description": "Research goal", "agent_type": "researcher", "dependencies": []},
                {"id": "task_2", "title": "Analysis Task", "description": "Analyze findings", "agent_type": "analyst", "dependencies": ["task_1"]},
                {"id": "task_3", "title": "Finalize", "description": "Finalize results", "agent_type": "supervisor", "dependencies": ["task_2"]},
            ]
        }

        return ChatResponse(
            id="deterministic",
            model=model,
            provider=self.provider_name,
            content=json.dumps(plan),
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            cost_cents=0,
            finish_reason="stop",
        )

    async def stream_chat(self, messages, model, temperature=0.7, max_tokens=None, tools=None):
        yield '{"tasks": []}'
        return

    def get_provider_name(self) -> str:
        return self.provider_name


# Factory - scaffold
def get_model_provider(provider_name: str = "openai-compatible") -> ModelProvider:
    """
    Factory for ModelProvider - scaffold
    provider_name: openai-compatible, anthropic, ollama, deterministic
    For Arena/OpenAI-compatible: use openai-compatible with base_url override via env
    """
    from app.config import settings

    if provider_name == "openai-compatible":
        # Arena fits here via ARENA_BASE_URL override
        base_url = settings.arena_base_url or settings.openai_base_url
        api_key = settings.arena_api_key or settings.openai_api_key
        return OpenAICompatibleProvider(api_key=api_key, base_url=base_url)
    elif provider_name == "anthropic":
        return AnthropicProvider(api_key=settings.anthropic_api_key)
    elif provider_name == "ollama":
        return OllamaProvider(base_url=settings.ollama_base_url)
    elif provider_name == "deterministic":
        return DeterministicProvider()
    else:
        # Default to openai-compatible
        return OpenAICompatibleProvider()
