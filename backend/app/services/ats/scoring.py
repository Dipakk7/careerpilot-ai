from app.core.ats_constants import SCORE_WEIGHTS
from app.core.config import settings

def round_score(val: float) -> int:
    """Helper to round float score half up to the nearest integer.
    Avoids Python's built-in banker's rounding (where round(10.5) is 10).
    """
    return int(val + 0.5) if val >= 0 else int(val - 0.5)

def score_contact(parsed_data: dict) -> int:
    """Score contact info. Max: SCORE_WEIGHTS['contact'].
    Rules: Name, Email, Phone present -> proportional score.
    """
    max_weight = SCORE_WEIGHTS.get("contact", 10)
    if not parsed_data or not isinstance(parsed_data, dict):
        return 0
    
    data = parsed_data.get("data", {})
    if not isinstance(data, dict):
        return 0
    
    def _is_present(field_key: str) -> bool:
        field = data.get(field_key)
        if isinstance(field, dict):
            val = field.get("value")
        elif hasattr(field, "value"):
            val = getattr(field, "value")
        else:
            val = field
        return bool(isinstance(val, str) and val.strip())
        
    present_count = sum(1 for f in ["name", "email", "phone"] if _is_present(f))
    score = round_score((present_count / 3.0) * max_weight)
    return min(max(score, 0), max_weight)

def score_skills(parsed_data: dict) -> int:
    """Score skills. Max: SCORE_WEIGHTS['skills'].
    Rules: Unique, non-empty skills.
    Scale score proportionally against settings.ATS_MIN_SKILLS_FOR_FULL_SCORE.
    """
    max_weight = SCORE_WEIGHTS.get("skills", 25)
    if not parsed_data or not isinstance(parsed_data, dict):
        return 0
    
    data = parsed_data.get("data", {})
    if not isinstance(data, dict):
        return 0
        
    skills_node = data.get("skills", {})
    if isinstance(skills_node, dict):
        skills_list = skills_node.get("value", [])
    elif hasattr(skills_node, "value"):
        skills_list = getattr(skills_node, "value", [])
    elif isinstance(skills_node, list):
        skills_list = skills_node
    else:
        skills_list = []
        
    if not isinstance(skills_list, list):
        skills_list = []
        
    unique_skills = set()
    for s in skills_list:
        if isinstance(s, str) and s.strip():
            unique_skills.add(s.strip().lower())
            
    min_skills = getattr(settings, "ATS_MIN_SKILLS_FOR_FULL_SCORE", 8)
    min_skills = max(min_skills, 1)
    
    count = len(unique_skills)
    if count >= min_skills:
        return max_weight
        
    score = round_score((count / min_skills) * max_weight)
    return min(max(score, 0), max_weight)

def score_education(parsed_data: dict) -> int:
    """Score education. Max: SCORE_WEIGHTS['education'].
    Rules:
    - 0 education -> 0
    - 1 entry -> 70%
    - 2+ entries -> Full score (100%)
    - Degree present increases confidence
    - Institution present required for full score
    """
    max_weight = SCORE_WEIGHTS.get("education", 15)
    if not parsed_data or not isinstance(parsed_data, dict):
        return 0
        
    data = parsed_data.get("data", {})
    if not isinstance(data, dict):
        return 0
        
    edu_node = data.get("education", {})
    if isinstance(edu_node, dict):
        edu_list = edu_node.get("value", [])
    elif hasattr(edu_node, "value"):
        edu_list = getattr(edu_node, "value", [])
    elif isinstance(edu_node, list):
        edu_list = edu_node
    else:
        edu_list = []
        
    if not isinstance(edu_list, list):
        return 0
        
    valid_entries = []
    for e in edu_list:
        if not isinstance(e, dict):
            continue
        if any(isinstance(v, str) and v.strip() for v in e.values() if v is not None):
            valid_entries.append(e)
            
    if not valid_entries:
        return 0
        
    def get_quality(entry: dict) -> float:
        inst = entry.get("institution")
        deg = entry.get("degree")
        has_inst = bool(isinstance(inst, str) and inst.strip())
        has_deg = bool(isinstance(deg, str) and deg.strip())
        
        if has_inst and has_deg:
            return 1.0
        elif has_inst and not has_deg:
            return 0.7
        elif not has_inst and has_deg:
            return 0.5
        else:
            return 0.1
            
    if len(valid_entries) == 1:
        quality = get_quality(valid_entries[0])
        score = round_score(0.7 * max_weight * quality)
    else:
        q1 = get_quality(valid_entries[0])
        q2 = get_quality(valid_entries[1])
        avg_quality = (q1 + q2) / 2.0
        score = round_score(max_weight * avg_quality)
        
    return min(max(score, 0), max_weight)

def score_experience(parsed_data: dict) -> int:
    """Score experience. Max: SCORE_WEIGHTS['experience'].
    Rules:
    - 0 experience -> 0
    - Title, Company, Duration, Description: each increases score.
    - Multiple entries receive higher score.
    - Uses settings.ATS_MIN_EXPERIENCE_ENTRIES.
    """
    max_weight = SCORE_WEIGHTS.get("experience", 25)
    if not parsed_data or not isinstance(parsed_data, dict):
        return 0
        
    data = parsed_data.get("data", {})
    if not isinstance(data, dict):
        return 0
        
    exp_node = data.get("experience", {})
    if isinstance(exp_node, dict):
        exp_list = exp_node.get("value", [])
    elif hasattr(exp_node, "value"):
        exp_list = getattr(exp_node, "value", [])
    elif isinstance(exp_node, list):
        exp_list = exp_node
    else:
        exp_list = []
        
    if not isinstance(exp_list, list):
        return 0
        
    valid_entries = []
    for e in exp_list:
        if not isinstance(e, dict):
            continue
        if any(isinstance(v, str) and v.strip() for v in e.values() if v is not None):
            valid_entries.append(e)
            
    if not valid_entries:
        return 0
        
    min_entries = getattr(settings, "ATS_MIN_EXPERIENCE_ENTRIES", 2)
    min_entries = max(min_entries, 1)
    
    qualities = []
    for entry in valid_entries:
        fields = ["title", "company", "duration", "description"]
        present_count = sum(1 for f in fields if isinstance(entry.get(f), str) and entry.get(f).strip())
        qualities.append(present_count / 4.0)
        
    qualities.sort(reverse=True)
    top_qualities = qualities[:min_entries]
    
    score = round_score(max_weight * (sum(top_qualities) / min_entries))
    return min(max(score, 0), max_weight)

def score_projects(parsed_data: dict) -> int:
    """Score projects. Max: SCORE_WEIGHTS['projects'].
    Rules: Name, Description, Technologies present -> proportional.
    """
    max_weight = SCORE_WEIGHTS.get("projects", 15)
    if not parsed_data or not isinstance(parsed_data, dict):
        return 0
        
    data = parsed_data.get("data", {})
    if not isinstance(data, dict):
        return 0
        
    proj_node = data.get("projects", {})
    if isinstance(proj_node, dict):
        proj_list = proj_node.get("value", [])
    elif hasattr(proj_node, "value"):
        proj_list = getattr(proj_node, "value", [])
    elif isinstance(proj_node, list):
        proj_list = proj_node
    else:
        proj_list = []
        
    if not isinstance(proj_list, list):
        return 0
        
    valid_entries = []
    for p in proj_list:
        if not isinstance(p, dict):
            continue
        if any(v is not None for v in p.values()):
            valid_entries.append(p)
            
    if not valid_entries:
        return 0
        
    target_projects = 2
    qualities = []
    for entry in valid_entries:
        name = entry.get("name")
        desc = entry.get("description")
        techs = entry.get("technologies", [])
        
        has_name = bool(isinstance(name, str) and name.strip())
        has_desc = bool(isinstance(desc, str) and desc.strip())
        
        has_techs = False
        if isinstance(techs, list):
            has_techs = any(isinstance(t, str) and t.strip() for t in techs)
            
        present_count = sum([has_name, has_desc, has_techs])
        qualities.append(present_count / 3.0)
        
    qualities.sort(reverse=True)
    top_qualities = qualities[:target_projects]
    
    score = round_score(max_weight * (sum(top_qualities) / target_projects))
    return min(max(score, 0), max_weight)

def score_certifications(parsed_data: dict) -> int:
    """Score certifications. Max: SCORE_WEIGHTS['certifications'].
    Rules:
    - 0 certifications -> 0
    - 1 certification -> Half score
    - 2+ certifications -> Full score
    """
    max_weight = SCORE_WEIGHTS.get("certifications", 10)
    if not parsed_data or not isinstance(parsed_data, dict):
        return 0
        
    data = parsed_data.get("data", {})
    if not isinstance(data, dict):
        return 0
        
    certs_node = data.get("certifications", {})
    if isinstance(certs_node, dict):
        certs_list = certs_node.get("value", [])
    elif hasattr(certs_node, "value"):
        certs_list = getattr(certs_node, "value", [])
    elif isinstance(certs_node, list):
        certs_list = certs_node
    else:
        certs_list = []
        
    if not isinstance(certs_list, list):
        return 0
        
    valid_certs = [c.strip() for c in certs_list if isinstance(c, str) and c.strip()]
    if not valid_certs:
        return 0
        
    if len(valid_certs) == 1:
        score = round_score(0.5 * max_weight)
    else:
        score = max_weight
        
    return min(max(score, 0), max_weight)


