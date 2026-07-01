import os
import yaml
from typing import Tuple
from app.ai.exceptions import InvalidPrompt
from app.ai.schemas.prompt_metadata import PromptMetadata, PromptTemplate

def parse_prompt_content(content: str, filepath_for_error: str = "unknown") -> Tuple[PromptMetadata, str]:
    """Parse raw file content containing YAML front matter and Jinja2 template body.

    Expected format:
    ---
    name: resume_review
    version: 1.0.0
    description: ATS Review prompt
    author: CareerPilot AI Team
    last_updated: 2026-07-01
    metadata:
      category: resume
    ---
    Template body goes here...
    """
    normalized_content = content.lstrip()
    if not normalized_content.startswith("---"):
        raise InvalidPrompt(
            f"Template at {filepath_for_error} does not start with front matter marker '---'."
        )

    # Split on '---' but limit to 3 parts:
    # 0: Empty string (before the first ---)
    # 1: The YAML block (between first and second ---)
    # 2: The template content (after second ---)
    parts = normalized_content.split("---", 2)
    if len(parts) < 3:
        raise InvalidPrompt(
            f"Template at {filepath_for_error} is missing closing front matter marker '---'."
        )

    front_matter_raw = parts[1].strip()
    template_body = parts[2].lstrip("\n")  # preserve leading indentation but drop leading newlines

    try:
        metadata_dict = yaml.safe_load(front_matter_raw)
        if not isinstance(metadata_dict, dict):
            raise InvalidPrompt(
                f"Template front matter at {filepath_for_error} is not a valid YAML dictionary."
            )
    except Exception as e:
        raise InvalidPrompt(
            f"Failed to parse YAML front matter in {filepath_for_error}: {e}"
        )

    # Validate required fields
    required_fields = ["name", "version", "description", "last_updated"]
    missing = [f for f in required_fields if f not in metadata_dict]
    if missing:
        raise InvalidPrompt(
            f"Template at {filepath_for_error} is missing required front matter fields: {', '.join(missing)}"
        )

    # Convert potentially auto-parsed types (like date or float) to strings for validation
    for key in ["version", "last_updated"]:
        if key in metadata_dict and not isinstance(metadata_dict[key], str):
            metadata_dict[key] = str(metadata_dict[key])

    try:
        # Validate metadata fields with Pydantic
        metadata = PromptMetadata(**metadata_dict)
    except Exception as e:
        raise InvalidPrompt(
            f"Metadata validation failed for template at {filepath_for_error}: {e}"
        )

    return metadata, template_body

def load_prompt_file(filepath: str) -> PromptTemplate:
    """Read a prompt file and return a PromptTemplate object containing parsed metadata & body.

    Args:
        filepath: Absolute path to the prompt template file.

    Returns:
        The constructed PromptTemplate object.

    Raises:
        InvalidPrompt: If file cannot be read or parsing fails.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        raise InvalidPrompt(f"Failed to read prompt file {filepath}: {e}")

    metadata, template_body = parse_prompt_content(content, filepath)
    return PromptTemplate(metadata=metadata, template_body=template_body)
