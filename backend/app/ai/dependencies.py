from fastapi import Depends
from app.ai.providers.base import BaseAIProvider
from app.ai.providers.factory import AIProviderFactory
from app.ai.services.ai_service import AIService


def get_ai_provider() -> BaseAIProvider:
    """Dependency injector to retrieve the configured AI provider.

    Returns:
        The active concrete AI provider based on settings.
    """
    return AIProviderFactory.get_provider()


def get_ai_service(
    provider: BaseAIProvider = Depends(get_ai_provider)
) -> AIService:
    """Dependency injector to retrieve the AIService instance.

    Args:
        provider: The active concrete AI provider (injected).

    Returns:
        The initialized AIService.
    """
    return AIService(provider)
