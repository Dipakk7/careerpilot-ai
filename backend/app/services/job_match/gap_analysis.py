from app.services.job_match.matcher import (
    match_skills,
    match_experience,
    match_education,
    match_certifications,
    match_keywords
)

def analyze_skill_gaps(
    resume_skills: list[str],
    required_skills: list[str],
    preferred_skills: list[str]
) -> dict:
    """
    Analyze skill gaps between resume and job description required and preferred skills.
    Returns matched, missing required, missing preferred, and extra resume skills.
    """
    res = match_skills(
        resume_skills=resume_skills,
        required_skills=required_skills,
        preferred_skills=preferred_skills
    )
    
    # matched includes both matched required and matched preferred, sorted alphabetically
    matched_skills = sorted(res["matched_required"] + res["matched_preferred"])
    
    return {
        "matched": matched_skills,
        "missing_required": res["missing_required"],
        "missing_preferred": res["missing_preferred"],
        "extra_resume_skills": res["extra_skills"]
    }

def analyze_experience_gap(
    resume_experience: list[dict],
    job_experience: list[str]
) -> dict:
    """
    Analyze experience gap (years of experience).
    """
    res = match_experience(
        resume_experience=resume_experience,
        job_experience=job_experience
    )
    
    req_years = res["details"]["required_years"]
    cand_years = res["details"]["candidate_years"]
    matched = res["matched"]
    
    required_str = f"{req_years:.1f} years"
    resume_str = f"{cand_years:.1f} years"
    
    if matched:
        gap_str = "0.0 years"
    else:
        gap_str = f"{max(0.0, req_years - cand_years):.1f} years"
        
    return {
        "matched": matched,
        "required": required_str,
        "resume": resume_str,
        "gap": gap_str
    }

def analyze_education_gap(
    resume_education: list[dict],
    job_education: list[str]
) -> dict:
    """
    Analyze education degree rank gap.
    """
    res = match_education(
        resume_education=resume_education,
        job_education=job_education
    )
    
    matched = res["matched"]
    
    resume_degrees = [
        e.get("degree") 
        for e in resume_education 
        if isinstance(e, dict) and e.get("degree")
    ]
    # Remove duplicates preserving order
    seen = set()
    unique_degrees = []
    for d in resume_degrees:
        d_clean = d.strip()
        if d_clean and d_clean.lower() not in seen:
            seen.add(d_clean.lower())
            unique_degrees.append(d_clean)
            
    required_str = ", ".join(job_education) if job_education else "None"
    resume_str = ", ".join(unique_degrees) if unique_degrees else "None"
    
    if matched:
        gap_str = "None"
    else:
        gap_str = f"Missing required degree level (Requires: {required_str})"
        
    return {
        "matched": matched,
        "required": required_str,
        "resume": resume_str,
        "gap": gap_str
    }

def analyze_certification_gap(
    resume_certifications: list[str],
    job_certifications: list[str]
) -> dict:
    """
    Analyze certification gap.
    """
    res = match_certifications(
        resume_certifications=resume_certifications,
        job_certifications=job_certifications
    )
    
    return {
        "matched": res["matched"],
        "missing": res["missing"]
    }

def analyze_keyword_gap(
    resume_keywords: list[str],
    job_keywords: list[str]
) -> dict:
    """
    Analyze keyword gap.
    """
    res = match_keywords(
        resume_keywords=resume_keywords,
        job_keywords=job_keywords
    )
    
    return {
        "matched": res["matched_keywords"],
        "missing": res["missing_keywords"]
    }
