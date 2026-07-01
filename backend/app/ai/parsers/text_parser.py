def parse_text(text: str) -> str:
    """Clean and return the raw response text.

    Args:
        text: The raw text response from the LLM.

    Returns:
        The stripped string.
    """
    return text.strip()
