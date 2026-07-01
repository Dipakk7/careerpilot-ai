import re
from typing import Optional, Any
from app.ai.parsers.json_parser import parse_json

def extract_code_block(text: str, language: Optional[str] = None) -> str:
    """Extract content from a markdown code block.

    If language is specified, matches that specific markdown code block.
    If no code block is found, returns the original text.

    Args:
        text: Raw text containing markdown formatting.
        language: The code block language identifier (e.g. 'json').

    Returns:
        The extracted code block content, or the original text stripped.
    """
    if language:
        pattern = rf"```(?:{re.escape(language)})\s*(.*?)\s*```"
    else:
        pattern = r"```(?:\w*)?\s*(.*?)\s*```"

    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def parse_json_from_markdown(text: str) -> Any:
    """Helper to extract a 'json' code block from markdown and parse it.

    Args:
        text: Raw markdown text containing a json code block.

    Returns:
        Parsed json object.
    """
    json_str = extract_code_block(text, "json")
    return parse_json(json_str)
