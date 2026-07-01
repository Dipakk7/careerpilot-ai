from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class PromptMetadata(BaseModel):
    """Metadata detailing the prompt name, version, author, and description."""
    name: str = Field(..., description="Unique name identifier for the prompt.")
    version: str = Field(..., description="Semantic version string (e.g. 1.0.0).")
    description: str = Field(..., description="A description of the prompt's purpose.")
    author: str = Field("CareerPilot AI Team", description="Author of the prompt template.")
    last_updated: str = Field(..., description="Date when this prompt version was last updated.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional custom metadata for the prompt.")

class PromptTemplate(BaseModel):
    """Holds a prompt template along with its metadata."""
    metadata: PromptMetadata = Field(..., description="The template metadata.")
    template_body: str = Field(..., description="The raw Jinja2 template content.")
