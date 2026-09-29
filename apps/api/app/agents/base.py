"""
BaseAgent - Scaffold Placeholder
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseAgent(ABC):
    """Scaffold placeholder for BaseAgent"""

    def __init__(self, agent_type: str, role: str):
        self.type = agent_type
        self.role = role

    @abstractmethod
    async def plan(self, task: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def act(self, step: Dict[str, Any]) -> Dict[str, Any]:
        pass
