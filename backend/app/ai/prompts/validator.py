from typing import Dict, Any, Set
from jinja2 import Environment, meta, TemplateSyntaxError
from app.ai.exceptions import InvalidPrompt

class PromptValidator:
    """Validates prompt template syntax and variables."""

    def __init__(self):
        self.env = Environment()

    def validate_template(self, template_body: str) -> Set[str]:
        """Check for Jinja2 template syntax errors and retrieve all undeclared variables.

        Args:
            template_body: The raw Jinja2 template string.

        Returns:
            A set of variable names expected by the template.

        Raises:
            InvalidPrompt: If the template has invalid syntax.
        """
        if not template_body or not template_body.strip():
            raise InvalidPrompt("Prompt template is empty.")

        try:
            ast = self.env.parse(template_body)
            return meta.find_undeclared_variables(ast)
        except TemplateSyntaxError as e:
            raise InvalidPrompt(f"Invalid template syntax at line {e.lineno}: {e.message}") from e

    def validate_variables(self, template_body: str, variables: Dict[str, Any]) -> None:
        """Verify that the variables provided match the template's expected variables exactly.

        Checks for missing or unknown (extra) variables.

        Args:
            template_body: The raw Jinja2 template content.
            variables: Context variables supplied for rendering.

        Raises:
            InvalidPrompt: If there are missing or unknown variables.
        """
        expected_vars = self.validate_template(template_body)
        provided_vars = set(variables.keys())

        missing = expected_vars - provided_vars
        if missing:
            raise InvalidPrompt(f"Missing required prompt variables: {', '.join(sorted(missing))}")

        unknown = provided_vars - expected_vars
        if unknown:
            raise InvalidPrompt(f"Unknown prompt variables provided: {', '.join(sorted(unknown))}")

    def validate_rendered_content(self, rendered_content: str) -> None:
        """Ensure that the rendered prompt is not empty or pure whitespace.

        Args:
            rendered_content: The fully rendered prompt string.

        Raises:
            InvalidPrompt: If the rendered prompt is empty.
        """
        if not rendered_content or not rendered_content.strip():
            raise InvalidPrompt("Rendered prompt is empty.")
