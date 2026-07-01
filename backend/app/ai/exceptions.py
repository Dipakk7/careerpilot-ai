class AIError(Exception):
    """Base exception for all AI-related errors."""
    pass


class AIProviderUnavailable(AIError):
    """Raised when the AI provider server is not reachable."""
    pass


class ModelNotFound(AIError):
    """Raised when the requested model is not available or loaded on the provider."""
    pass


class AIRequestTimeout(AIError):
    """Raised when the request to the AI provider times out."""
    pass


class InvalidPrompt(AIError):
    """Raised when the input prompt is invalid or rejected."""
    pass


class ResponseParsingError(AIError):
    """Raised when the AI response could not be parsed into the expected format."""
    pass
