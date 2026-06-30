import re
from app.core.ats_constants import ACTION_VERBS, WEAK_PHRASES

def count_action_verbs(text: str) -> int:
    """Counts occurrences of action verbs in the text (case-insensitive with word boundaries)."""
    if not text or not isinstance(text, str):
        return 0
    count = 0
    for verb in ACTION_VERBS:
        pattern = rf"\b{re.escape(verb)}\b"
        count += len(re.findall(pattern, text, re.IGNORECASE))
    return count

def count_weak_phrases(text: str) -> int:
    """Counts occurrences of weak phrases in the text (case-insensitive with word boundaries)."""
    if not text or not isinstance(text, str):
        return 0
    count = 0
    for phrase in WEAK_PHRASES:
        pattern = rf"\b{re.escape(phrase)}\b"
        count += len(re.findall(pattern, text, re.IGNORECASE))
    return count

def _extract_all_text(data) -> str:
    """Helper to recursively extract all text from parsed data dictionary structures,
    ignoring 'confidence' keys to avoid float values.
    """
    if isinstance(data, str):
        return data
    elif isinstance(data, list):
        return " ".join(_extract_all_text(item) for item in data)
    elif isinstance(data, dict):
        parts = []
        for k, v in data.items():
            if k == "confidence":
                continue
            parts.append(_extract_all_text(v))
        return " ".join(parts)
    else:
        return ""

def _get_list_value(data: dict, key: str) -> list:
    """Helper to extract a list field from parsed data structure."""
    node = data.get(key, {})
    if isinstance(node, dict):
        lst = node.get("value", [])
    elif hasattr(node, "value"):
        lst = getattr(node, "value", [])
    elif isinstance(node, list):
        lst = node
    else:
        lst = []
    if not isinstance(lst, list):
        return []
    return lst

def _is_field_present(data: dict, field_key: str) -> bool:
    """Helper to check if a simple field is present (non-empty string)."""
    field = data.get(field_key)
    if isinstance(field, dict):
        val = field.get("value")
    elif hasattr(field, "value"):
        val = getattr(field, "value")
    else:
        val = field
    return bool(isinstance(val, str) and val.strip())

def calculate_keyword_density(parsed_data: dict) -> float:
    """Calculates the keyword density as a percentage:
    (occurrences of unique skills in parsed text / total word count) * 100
    """
    if not parsed_data or not isinstance(parsed_data, dict):
        return 0.0
    data = parsed_data.get("data", {})
    if not isinstance(data, dict):
        return 0.0
    
    text = _extract_all_text(data)
    words = re.findall(r"\b\w+\b", text.lower())
    if not words:
        return 0.0
    
    skills_list = _get_list_value(data, "skills")
    unique_skills = {s.strip().lower() for s in skills_list if isinstance(s, str) and s.strip()}
    if not unique_skills:
        return 0.0
    
    match_count = 0
    for skill in unique_skills:
        pattern = rf"\b{re.escape(skill)}\b"
        match_count += len(re.findall(pattern, text.lower()))
        
    return round((match_count / len(words)) * 100.0, 2)

def calculate_section_completeness(parsed_data: dict) -> dict[str, bool]:
    """Determines completeness for the 6 core resume sections."""
    completeness = {
        "contact": False,
        "skills": False,
        "education": False,
        "experience": False,
        "projects": False,
        "certifications": False
    }
    if not parsed_data or not isinstance(parsed_data, dict):
        return completeness
    
    data = parsed_data.get("data", {})
    if not isinstance(data, dict):
        return completeness
    
    # 1. contact: True if name, email, and phone are present
    completeness["contact"] = (
        _is_field_present(data, "name") and
        _is_field_present(data, "email") and
        _is_field_present(data, "phone")
    )
    
    # 2. skills: True if >= 1 non-empty skill
    skills_list = _get_list_value(data, "skills")
    completeness["skills"] = any(isinstance(s, str) and s.strip() for s in skills_list)
    
    # 3. education: True if >= 1 valid education entry
    edu_list = _get_list_value(data, "education")
    completeness["education"] = any(
        isinstance(e, dict) and any(isinstance(v, str) and v.strip() for v in e.values() if v is not None)
        for e in edu_list
    )
    
    # 4. experience: True if >= 1 valid experience entry
    exp_list = _get_list_value(data, "experience")
    completeness["experience"] = any(
        isinstance(e, dict) and any(isinstance(v, str) and v.strip() for v in e.values() if v is not None)
        for e in exp_list
    )
    
    # 5. projects: True if >= 1 valid project entry
    proj_list = _get_list_value(data, "projects")
    completeness["projects"] = any(
        isinstance(p, dict) and any(v is not None for v in p.values())
        for p in proj_list
    )
    
    # 6. certifications: True if >= 1 valid certification
    certs_list = _get_list_value(data, "certifications")
    completeness["certifications"] = any(isinstance(c, str) and c.strip() for c in certs_list)
    
    return completeness

def count_empty_sections(parsed_data: dict) -> int:
    """Counts the number of core sections that are incomplete (False)."""
    completeness = calculate_section_completeness(parsed_data)
    return sum(1 for v in completeness.values() if not v)

def calculate_resume_length(raw_text: str) -> int:
    """Calculates resume length (word count)."""
    if not raw_text or not isinstance(raw_text, str):
        return 0
    return len(raw_text.split())
