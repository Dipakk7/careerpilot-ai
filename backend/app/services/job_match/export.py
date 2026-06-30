import json
from fastapi.encoders import jsonable_encoder
import uuid
from datetime import datetime

def _get_match_and_gap_dicts(result) -> tuple[dict, dict]:
    """
    Standardize different formats of result objects/dictionaries into match and gap dictionaries.
    """
    if isinstance(result, dict):
        match_data = result.get("match")
        gap_data = result.get("gap")
        if match_data is None:
            match_data = result
        if gap_data is None:
            gap_data = result
    else:
        match_data = getattr(result, "match", result)
        gap_data = getattr(result, "gap", result)

    # Convert Pydantic models/objects to dictionaries
    if hasattr(match_data, "model_dump"):
        match_dict = match_data.model_dump()
    elif hasattr(match_data, "dict"):
        match_dict = match_data.dict()
    else:
        match_dict = jsonable_encoder(match_data)

    if hasattr(gap_data, "model_dump"):
        gap_dict = gap_data.model_dump()
    elif hasattr(gap_data, "dict"):
        gap_dict = gap_data.dict()
    else:
        gap_dict = jsonable_encoder(gap_data)

    return match_dict, gap_dict

def generate_match_json(result) -> str:
    """
    Generate a formatted, serializable JSON string representing the combined match and gap analysis.
    """
    match_dict, gap_dict = _get_match_and_gap_dicts(result)
    
    # Construct a flat/merged dictionary for a cleaner export representation
    combined = {
        "resume_id": match_dict.get("resume_id") or gap_dict.get("resume_id"),
        "match_score": match_dict.get("match_score"),
        "grade": match_dict.get("grade"),
        "breakdown": match_dict.get("breakdown"),
        "matched_skills": match_dict.get("matched_skills", []),
        "missing_skills": match_dict.get("missing_skills", []),
        "extra_skills": match_dict.get("extra_skills", []),
        "recommendations": match_dict.get("recommendations", []),
        "overall_match": gap_dict.get("overall_match"),
        "skill_gap": gap_dict.get("skill_gap"),
        "experience_gap": gap_dict.get("experience_gap"),
        "education_gap": gap_dict.get("education_gap"),
        "certification_gap": gap_dict.get("certification_gap"),
        "keyword_gap": gap_dict.get("keyword_gap"),
        "priority_improvements": gap_dict.get("priority_improvements", []),
        "parser_version": match_dict.get("parser_version"),
        "ats_version": match_dict.get("ats_version"),
        "job_match_version": match_dict.get("job_match_version"),
        "generated_at": match_dict.get("generated_at"),
        "processing_time_ms": match_dict.get("processing_time_ms")
    }
    
    # Handle serialization of datetimes, UUIDs, etc.
    serializable = jsonable_encoder(combined)
    return json.dumps(serializable, indent=2)

def generate_match_markdown(result) -> str:
    """
    Generate a human-readable Markdown report from the match and gap analysis results.
    """
    match_dict, gap_dict = _get_match_and_gap_dicts(result)
    
    overall_score = match_dict.get("match_score", 0)
    grade = match_dict.get("grade", "Poor")
    overall_match = gap_dict.get("overall_match", False)
    breakdown = match_dict.get("breakdown") or {}
    
    matched_skills = match_dict.get("matched_skills") or []
    missing_skills = match_dict.get("missing_skills") or []
    
    edu_gap = gap_dict.get("education_gap") or {}
    exp_gap = gap_dict.get("experience_gap") or {}
    cert_gap = gap_dict.get("certification_gap") or {}
    
    recs = match_dict.get("recommendations") or []
    priority_improvements = gap_dict.get("priority_improvements") or []
    
    # Format skills
    matched_skills_str = ", ".join(matched_skills) if matched_skills else "None"
    missing_skills_str = ", ".join(missing_skills) if missing_skills else "None"
    
    # Format certifications
    cert_matched = cert_gap.get("matched") or []
    cert_missing = cert_gap.get("missing") or []
    cert_matched_str = ", ".join(cert_matched) if cert_matched else "None"
    cert_missing_str = ", ".join(cert_missing) if cert_missing else "None"
    
    # Format recommendations
    rec_lines = []
    for r in recs:
        cat = str(r.get("category", "")).capitalize()
        prio = str(r.get("priority", "")).upper()
        msg = r.get("message", "")
        rec_lines.append(f"- **[{prio}]** ({cat}): {msg}")
    recommendations_str = "\n".join(rec_lines) if rec_lines else "*No recommendations available.*"
    
    # Format priority improvements
    imp_lines = []
    for imp in priority_improvements:
        prio = str(imp.get("priority", "")).upper()
        cat = str(imp.get("category", "")).capitalize()
        msg = imp.get("message", "")
        imp_lines.append(f"- **[{prio}]** ({cat}): {msg}")
    improvements_str = "\n".join(imp_lines) if imp_lines else "*No priority improvements identified.*"
    
    # Build Markdown string
    md = f"""# Job Match & Gap Analysis Report

## Overall Match
- **Match Score**: {overall_score}%
- **Grade**: {grade}
- **Meets Core Requirements**: {"Yes" if overall_match else "No"}

## Score Breakdown
- **Skills Match**: {breakdown.get("skills", 0)}%
- **Experience Match**: {breakdown.get("experience", 0)}%
- **Education Match**: {breakdown.get("education", 0)}%
- **Certifications Match**: {breakdown.get("certifications", 0)}%
- **Keywords Match**: {breakdown.get("keywords", 0)}%

## Matched Skills
{matched_skills_str}

## Missing Skills
{missing_skills_str}

## Education Gap
- **Required**: {edu_gap.get("required", "Not specified")}
- **Resume**: {edu_gap.get("resume", "Not found")}
- **Gap Details**: {edu_gap.get("gap", "No gap detected")}
- **Status**: {"Matched" if edu_gap.get("matched", False) else "Gap Identified"}

## Experience Gap
- **Required**: {exp_gap.get("required", "Not specified")}
- **Resume**: {exp_gap.get("resume", "Not found")}
- **Gap Details**: {exp_gap.get("gap", "No gap detected")}
- **Status**: {"Matched" if exp_gap.get("matched", False) else "Gap Identified"}

## Certification Gap
- **Matched**: {cert_matched_str}
- **Missing**: {cert_missing_str}

## Recommendations
{recommendations_str}

## Priority Improvements
{improvements_str}
"""
    return md
