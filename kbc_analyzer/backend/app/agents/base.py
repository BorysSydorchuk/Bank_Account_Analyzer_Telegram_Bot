"""Abstract base agent. Every agent (categorization, insight, and whatever
Sprint 3 adds) is a thin subclass of this, holding a provider and doing its
one job in run().
"""
from abc import ABC, abstractmethod

from .providers.base import LLMProvider

__all__ = ["BaseAgent"]


class BaseAgent(ABC):
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    @abstractmethod
    async def run(self, **kwargs) -> dict:
        """Execute the agent. Returns a structured result."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name for logging."""
