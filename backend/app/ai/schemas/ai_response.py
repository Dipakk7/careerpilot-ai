from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

class TokenUsage(BaseModel):
    """Details of token usage for the prompt and generated response."""
    prompt_tokens: int = Field(0, description="Number of tokens in the prompt.")
    completion_tokens: int = Field(0, description="Number of tokens in the completion.")
    total_tokens: int = Field(0, description="Total number of tokens used.")

class AIStructuredResponse(BaseModel):
    """The unified schema returned by the AI Service Layer to business logic."""
    provider: str = Field(..., description="The active concrete AI provider name (e.g. 'ollama').")
    model: str = Field(..., description="The specific model used for generation.")
    latency_ms: float = Field(..., description="Total elapsed latency in milliseconds.")
    prompt_version: str = Field(..., description="The version string of the prompt template used.")
    created_at: datetime = Field(..., description="ISO timestamp when the response was created.")
    raw_response: Dict[str, Any] = Field(default_factory=dict, description="The raw response from the underlying provider client.")
    parsed_response: Any = Field(..., description="Strongly typed or parsed object (dict, list, or string).")
    usage: TokenUsage = Field(default_factory=TokenUsage, description="Token usage metadata.")
    token_fields: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for future token tracking.")
