from app.schemas.job_match import MatchBreakdown
from app.core.job_match_constants import MATCH_WEIGHTS

def calculate_match_breakdown(
    skills_score: int,
    experience_score: int,
    education_score: int,
    certifications_score: int,
    keywords_score: int
) -> MatchBreakdown:
    """
    Calculate the matching breakdown across skills, experience, education, certifications, and keywords.
    """
    return MatchBreakdown(
        skills=skills_score,
        experience=experience_score,
        education=education_score,
        certifications=certifications_score,
        keywords=keywords_score
    )

def calculate_match_score(breakdown: MatchBreakdown) -> int:
    """
    Calculate the overall match score between 0 and 100 based on MATCH_WEIGHTS.
    """
    score = 0.0
    for key, weight in MATCH_WEIGHTS.items():
        val = getattr(breakdown, key, 0)
        score += val * (weight / 100.0)
    # Round to nearest integer (half up) and clamp between 0 and 100
    overall = int(score + 0.5)
    return max(0, min(100, overall))

def find_missing_items(
    missing_skills: list[str],
    missing_education: list[str],
    missing_certifications: list[str],
    missing_experience: list[str],
    missing_keywords: list[str]
) -> dict:
    """
    Identify job description requirements that are missing in the resume.
    """
    return {
        "skills": missing_skills,
        "education": missing_education,
        "certifications": missing_certifications,
        "experience": missing_experience,
        "keywords": missing_keywords
    }

def find_extra_items(
    extra_skills: list[str],
    extra_certifications: list[str] = None
) -> dict:
    """
    Identify skills/certifications in the resume that are not requested in the job description.
    """
    return {
        "skills": extra_skills,
        "certifications": extra_certifications or []
    }

def find_missing_skills(resume_skills: list[str], required_skills: list[str], preferred_skills: list[str]) -> list[str]:
    """Legacy helper: Identify required/preferred job description skills that are missing in the resume."""
    from app.services.job_match.matcher import match_skills
    match_res = match_skills(resume_skills, required_skills, preferred_skills)
    return match_res["missing_required"] + match_res["missing_preferred"]

def find_extra_skills(resume_skills: list[str], required_skills: list[str], preferred_skills: list[str]) -> list[str]:
    """Legacy helper: Identify skills in the resume that are not requested in the job description."""
    from app.services.job_match.matcher import match_skills
    match_res = match_skills(resume_skills, required_skills, preferred_skills)
    return match_res["extra_skills"]

