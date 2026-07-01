import json
from typing import Any
from app.ai.exceptions import ResponseParsingError

def parse_json(text: str) -> Any:
    """Parse a string response as JSON.

    Args:
        text: The text response from the LLM.

    Returns:
        The parsed Python object (dict or list).

    Raises:
        ResponseParsingError: If the text is not valid JSON.
    """
    cleaned = text.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ResponseParsingError(f"Failed to parse JSON response: {e}. Raw response: {text}") from e
