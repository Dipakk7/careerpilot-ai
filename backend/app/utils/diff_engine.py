import json
import difflib
from typing import Dict, List, Any

def compute_diff(original: Any, rewritten: Any) -> Dict[str, Any]:
    """Compare original and rewritten content to find added, removed, and modified blocks.

    Supports strings, lists of strings, dicts, or other structures by converting them to text.
    Returns a dictionary matching the SectionDiff schema:
    {
        "added": [...],
        "removed": [...],
        "modified": [{"from": "...", "to": "..."}]
    }
    """
    # 1. Normalize both inputs to strings
    original_str = _normalize_to_string(original)
    rewritten_str = _normalize_to_string(rewritten)

    # 2. Split into words for word-level diff
    original_words = original_str.split()
    rewritten_words = rewritten_str.split()

    matcher = difflib.SequenceMatcher(None, original_words, rewritten_words)
    
    added: List[str] = []
    removed: List[str] = []
    modified: List[Dict[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            from_text = " ".join(original_words[i1:i2])
            to_text = " ".join(rewritten_words[j1:j2])
            modified.append({"from": from_text, "to": to_text})
        elif tag == "delete":
            removed_text = " ".join(original_words[i1:i2])
            removed.append(removed_text)
        elif tag == "insert":
            added_text = " ".join(rewritten_words[j1:j2])
            added.append(added_text)

    return {
        "added": added,
        "removed": removed,
        "modified": modified
    }

def _normalize_to_string(value: Any) -> str:
    """Normalize input value to a clean string representation."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        # Join bullet points or list items with a newline
        return "\n".join(_normalize_to_string(item) for item in value)
    if isinstance(value, dict):
        # Format dictionary keys and values into a readable textual list
        lines = []
        for k, v in value.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            elif isinstance(v, dict):
                lines.append(f"{k}:")
                for sub_k, sub_v in v.items():
                    lines.append(f"  {sub_k}: {sub_v}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)
    return str(value).strip()
