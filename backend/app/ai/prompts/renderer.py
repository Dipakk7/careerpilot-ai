from typing import Dict, Any, Optional
import os
from jinja2 import Environment, FileSystemLoader
from app.ai.exceptions import InvalidPrompt
from app.ai.config import PROMPT_TEMPLATE_PATH

class PromptRenderer:
    """Renders prompt templates with Jinja2, resolving blocks, loops, and conditionals."""

    def __init__(self, template_dir: Optional[str] = None):
        """Initialize the Jinja2 rendering environment.

        Args:
            template_dir: Base directory for templates. Defaults to PROMPT_TEMPLATE_PATH config.
        """
        self.template_dir = template_dir or PROMPT_TEMPLATE_PATH
        if self.template_dir and os.path.exists(self.template_dir):
            self.env = Environment(loader=FileSystemLoader(self.template_dir))
        else:
            self.env = Environment()

    def render(self, template_body: str, variables: Dict[str, Any]) -> str:
        """Render a raw template body string with context variables.

        Args:
            template_body: The raw Jinja2 template content.
            variables: Context dictionary of variables to inject.

        Returns:
            The rendered prompt text.

        Raises:
            InvalidPrompt: If rendering fails due to syntax or execution errors.
        """
        try:
            template = self.env.from_string(template_body)
            return template.render(**variables)
        except Exception as e:
            raise InvalidPrompt(f"Failed to render prompt: {e}") from e
