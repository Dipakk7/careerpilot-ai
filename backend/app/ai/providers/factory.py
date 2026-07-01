from typing import Optional
from app.ai.providers.base import BaseAIProvider
from app.ai.providers.ollama import OllamaProvider
from app.core.config import settings
from app.ai.exceptions import AIError


class AIProviderFactory:
    """Factory to instantiate AI providers dynamically based on settings."""

    @staticmethod
    def get_provider(provider_name: Optional[str] = None, model_name: Optional[str] = None) -> BaseAIProvider:
        """Resolve and return the appropriate AI provider.

        Args:
            provider_name: Optional override for the provider. If None, loaded from settings.
            model_name: Optional override for the model. If None, loaded from settings.

        Returns:
            An instance of BaseAIProvider.

        Raises:
            AIError if provider is unsupported.
        """
        name = (provider_name or settings.AI_PROVIDER).lower()
        if name == "ollama":
            model = model_name or settings.OLLAMA_MODEL
            return OllamaProvider(
                host=settings.OLLAMA_HOST,
                model=model,
                timeout=float(settings.AI_TIMEOUT)
            )
        else:
            raise AIError(f"Unsupported AI provider: '{name}'")
