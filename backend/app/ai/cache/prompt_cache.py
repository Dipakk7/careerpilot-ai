import json
import hashlib
import time
import threading
from typing import Dict, Any, Optional, Tuple
from app.ai.schemas.ai_response import AIStructuredResponse

class PromptCache:
    """In-memory, thread-safe cache for AI prompt responses with TTL support."""

    def __init__(self):
        self._cache: Dict[str, Tuple[AIStructuredResponse, float]] = {}
        self._lock = threading.Lock()

    def _generate_key(
        self, provider: str, model: str, prompt_version: str, variables: Dict[str, Any]
    ) -> str:
        """Create a stable, unique SHA-256 hash key for cache lookup.

        Args:
            provider: The name of the AI provider.
            model: The name of the model.
            prompt_version: The version string of the prompt.
            variables: Context variables passed during prompt rendering.

        Returns:
            A unique SHA-256 hash string.
        """
        # Serialize variables to stable JSON sorted by key
        serialized_vars = json.dumps(variables, sort_keys=True, default=str)
        raw_key = f"{provider}:{model}:{prompt_version}:{serialized_vars}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(
        self, provider: str, model: str, prompt_version: str, variables: Dict[str, Any]
    ) -> Optional[AIStructuredResponse]:
        """Retrieve a cached response if valid and not expired.

        Args:
            provider: The name of the AI provider.
            model: The name of the model.
            prompt_version: The version string of the prompt.
            variables: Context variables passed during prompt rendering.

        Returns:
            The cached AIStructuredResponse, or None if not found/expired.
        """
        key = self._generate_key(provider, model, prompt_version, variables)
        with self._lock:
            if key in self._cache:
                response, expiry = self._cache[key]
                if time.time() < expiry:
                    return response
                else:
                    # Expired entry, remove it
                    del self._cache[key]
            return None

    def set(
        self,
        provider: str,
        model: str,
        prompt_version: str,
        variables: Dict[str, Any],
        response: AIStructuredResponse,
        ttl: int = 300,
    ) -> None:
        """Store a response in the cache with a time-to-live.

        Args:
            provider: The name of the AI provider.
            model: The name of the model.
            prompt_version: The version string of the prompt.
            variables: Context variables passed during prompt rendering.
            response: The response object to cache.
            ttl: Time-to-live in seconds.
        """
        if ttl <= 0:
            return
        key = self._generate_key(provider, model, prompt_version, variables)
        expiry = time.time() + ttl
        with self._lock:
            self._cache[key] = (response, expiry)

    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Get the number of active cached items (includes potentially expired ones)."""
        with self._lock:
            return len(self._cache)
