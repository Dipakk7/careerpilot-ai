import re
from app.schemas.ats import ATSRecommendation
from app.core.config import settings
from app.core.ats_constants import SCORE_WEIGHTS
from app.services.ats.metrics import (
    count_action_verbs,
    count_weak_phrases,
    _extract_all_text,
    _get_list_value,
    _is_field_present,
)

def get_breakdown_value(breakdown, key: str) -> int:
    """Safely extracts score from a breakdown dictionary or object."""
    if isinstance(breakdown, dict):
        return breakdown.get(key, 0)
    elif hasattr(breakdown, key):
        return getattr(breakdown, key, 0)
    return 0

def generate_strengths(parsed_data: dict, breakdown: dict) -> list[str]:
    """Identify resume strengths. Maximum 10 strengths, no duplicates."""
    strengths = []
    if not parsed_data or not isinstance(parsed_data, dict):
        return strengths
        
    data = parsed_data.get("data", {})
    if not isinstance(data, dict):
        return strengths

    # 1. Complete contact information
    has_complete_contact = _is_field_present(data, "name") and _is_field_present(data, "email") and _is_field_present(data, "phone")
    if has_complete_contact:
        strengths.append("Complete contact information")
        
    # 2. Strong technical skills
    skills_list = _get_list_value(data, "skills")
    unique_skills = {s.strip().lower() for s in skills_list if isinstance(s, str) and s.strip()}
    min_skills = getattr(settings, "ATS_MIN_SKILLS_FOR_FULL_SCORE", 8)
    if len(unique_skills) >= min_skills:
        strengths.append("Strong technical skills")
        
    # 3. Multiple projects
    projects_list = _get_list_value(data, "projects")
    valid_projects = [p for p in projects_list if isinstance(p, dict) and any(v is not None for v in p.values())]
    if len(valid_projects) >= 2:
        strengths.append("Multiple projects")
        
    # 4. Experience section complete
    exp_list = _get_list_value(data, "experience")
    valid_exp = [e for e in exp_list if isinstance(e, dict) and any(isinstance(v, str) and v.strip() for v in e.values() if v is not None)]
    min_exp = getattr(settings, "ATS_MIN_EXPERIENCE_ENTRIES", 2)
    if len(valid_exp) >= min_exp:
        strengths.append("Experience section complete")
        
    # 5. Certifications present
    certs_list = _get_list_value(data, "certifications")
    valid_certs = [c for c in certs_list if isinstance(c, str) and c.strip()]
    if len(valid_certs) >= 1:
        strengths.append("Certifications present")
        
    # 6. Well structured education
    edu_list = _get_list_value(data, "education")
    valid_edu = [e for e in edu_list if isinstance(e, dict) and any(isinstance(v, str) and v.strip() for v in e.values() if v is not None)]
    has_well_structured_edu = False
    if valid_edu:
        for entry in valid_edu:
            inst = entry.get("institution")
            deg = entry.get("degree")
            if isinstance(inst, str) and inst.strip() and isinstance(deg, str) and deg.strip():
                has_well_structured_edu = True
                break
    if has_well_structured_edu:
        strengths.append("Well structured education")

    # 7. Professional portfolio links
    links_list = _get_list_value(data, "links")
    valid_links = [l for l in links_list if isinstance(l, str) and l.strip()]
    if len(valid_links) >= 1:
        strengths.append("Professional portfolio links")

    # Remove duplicates preserving order
    unique_strengths = list(dict.fromkeys(strengths))
    return unique_strengths[:10]

def generate_weaknesses(parsed_data: dict, breakdown: dict) -> list[str]:
    """Identify resume weaknesses. Maximum 10 weaknesses, no duplicates."""
    weaknesses = []
    if not parsed_data or not isinstance(parsed_data, dict):
        return weaknesses
        
    data = parsed_data.get("data", {})
    if not isinstance(data, dict):
        return weaknesses

    # 1. Missing phone number
    if not _is_field_present(data, "phone"):
        weaknesses.append("Missing phone number")
        
    # 2. Missing email address
    if not _is_field_present(data, "email"):
        weaknesses.append("Missing email address")
        
    # 3. Few technical skills
    skills_list = _get_list_value(data, "skills")
    unique_skills = {s.strip().lower() for s in skills_list if isinstance(s, str) and s.strip()}
    min_skills = getattr(settings, "ATS_MIN_SKILLS_FOR_FULL_SCORE", 8)
    if not unique_skills:
        weaknesses.append("No technical skills listed")
    elif len(unique_skills) < min_skills:
        weaknesses.append("Few technical skills")
        
    # 4. No certifications
    certs_list = _get_list_value(data, "certifications")
    valid_certs = [c for c in certs_list if isinstance(c, str) and c.strip()]
    if not valid_certs:
        weaknesses.append("No certifications")
        
    # 5. Projects missing technologies
    projects_list = _get_list_value(data, "projects")
    valid_projects = [p for p in projects_list if isinstance(p, dict) and any(v is not None for v in p.values())]
    if not valid_projects:
        weaknesses.append("No projects listed")
    else:
        missing_tech = False
        for proj in valid_projects:
            techs = proj.get("technologies", [])
            if not isinstance(techs, list) or not any(isinstance(t, str) and t.strip() for t in techs):
                missing_tech = True
                break
        if missing_tech:
            weaknesses.append("Projects missing technologies")
            
    # 6. Experience descriptions too short
    exp_list = _get_list_value(data, "experience")
    valid_exp = [e for e in exp_list if isinstance(e, dict) and any(isinstance(v, str) and v.strip() for v in e.values() if v is not None)]
    if not valid_exp:
        weaknesses.append("No work experience listed")
    else:
        short_desc = False
        for exp in valid_exp:
            desc = exp.get("description", "")
            if not isinstance(desc, str) or len(desc.split()) < 10:
                short_desc = True
                break
        if short_desc:
            weaknesses.append("Experience descriptions too short")
            
    # 7. No education history listed
    edu_list = _get_list_value(data, "education")
    valid_edu = [e for e in edu_list if isinstance(e, dict) and any(isinstance(v, str) and v.strip() for v in e.values() if v is not None)]
    if not valid_edu:
        weaknesses.append("No education history listed")

    # 8. No action verbs
    combined_text = _extract_all_text(data)
    if count_action_verbs(combined_text) == 0:
        weaknesses.append("No action verbs")
        
    # 9. Weak resume language
    if count_weak_phrases(combined_text) > 0:
        weaknesses.append("Weak resume language")

    # Remove duplicates preserving order
    unique_weaknesses = list(dict.fromkeys(weaknesses))
    return unique_weaknesses[:10]

def generate_recommendations(parsed_data: dict, breakdown: dict) -> list[ATSRecommendation]:
    """Generate structured improvement suggestions. Return list[ATSRecommendation]."""
    recommendations = []
    if not parsed_data or not isinstance(parsed_data, dict):
        return recommendations
        
    data = parsed_data.get("data", {})
    if not isinstance(data, dict):
        return recommendations

    # For each category in SCORE_WEIGHTS, check if there's room for improvement (score < max_weight)
    for category, max_weight in SCORE_WEIGHTS.items():
        score = get_breakdown_value(breakdown, category)
        
        # If score is already at maximum, we don't need to recommend anything for it.
        if score >= max_weight:
            continue
            
        # Calculate percentage
        percentage = (score / max_weight) * 100.0 if max_weight > 0 else 0.0
        
        # Priority rules
        if percentage < 50.0:
            priority = "high"
        elif percentage <= 80.0:
            priority = "medium"
        else:
            priority = "low"
            
        # Message based on category and score
        if category == "contact":
            if score == 0:
                message = "Add missing contact details: ensure Name, Email, and Phone number are present."
            else:
                message = "Ensure your phone number and professional links (e.g., LinkedIn, GitHub) are complete."
        elif category == "skills":
            if score == 0:
                message = "Add more relevant technical skills to match industry standards."
            else:
                message = "Expand your technical skills section with more specialized tools and frameworks."
        elif category == "education":
            if score == 0:
                message = "Add your education history, including degree, institution, and graduation year."
            else:
                message = "Ensure all education entries include both the degree name and institution."
        elif category == "experience":
            if score == 0:
                message = "Add professional work experience with clear titles, companies, and descriptions."
            else:
                message = "Improve experience descriptions by adding action verbs and focusing on achievements."
        elif category == "projects":
            if score == 0:
                message = "Add at least two key projects with descriptions to showcase your practical skills."
            else:
                message = "Include technologies used in each project description."
        elif category == "certifications":
            if score == 0:
                message = "Add relevant professional certifications to boost credibility."
            else:
                message = "Add more certifications related to your target field."
        else:
            message = f"Improve the {category} section of your resume."
            
        recommendations.append(
            ATSRecommendation(
                category=category,
                priority=priority,
                message=message
            )
        )
        
    # Sort recommendations: high priority first, then medium, then low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))
    
    # Limit using settings.ATS_RECOMMENDATION_LIMIT
    limit = getattr(settings, "ATS_RECOMMENDATION_LIMIT", 8)
    return recommendations[:limit]
