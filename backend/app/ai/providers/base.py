from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.ai.schemas.ai import AIRequest, AIResponse


class BaseAIProvider(ABC):
    """Abstract base class defining the standard interface for all AI/LLM providers."""

    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        """Perform a single prompt generation request.

        Args:
            request: The standard AI request schema.

        Returns:
            The standard AI response schema.
        """
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        **kwargs
    ) -> AIResponse:
        """Perform a chat completions interaction.

        Args:
            messages: A list of messages (role/content dicts).
            system: Optional system instruction.
            kwargs: Extra parameters to pass through to the provider.

        Returns:
            The standard AI response schema.
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check status, reachability, and model availability of the provider.

        Returns:
            Dict containing the health status details.
        """
        pass
