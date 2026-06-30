from app.schemas.job_match import MatchRecommendation
from app.core.config import settings

def generate_job_recommendations(
    missing_skills: list[str],
    missing_education: list[str],
    missing_certifications: list[str],
    missing_experience: list[str],
    missing_keywords: list[str],
    missing_preferred_skills: list[str] = None
) -> list[MatchRecommendation]:
    """
    Generate targeted recommendations to improve the match between a resume and a job description.
    """
    recs = []
    
    # Missing required skills -> HIGH
    for skill in missing_skills:
        recs.append(MatchRecommendation(
            category="skills",
            priority="high",
            message=f"Add missing required skill: {skill}"
        ))
        
    # Missing experience -> HIGH
    for exp in missing_experience:
        recs.append(MatchRecommendation(
            category="experience",
            priority="high",
            message=exp
        ))
        
    # Missing preferred skills -> MEDIUM
    if missing_preferred_skills:
        for skill in missing_preferred_skills:
            recs.append(MatchRecommendation(
                category="skills",
                priority="medium",
                message=f"Add missing preferred skill: {skill}"
            ))

    # Missing education -> MEDIUM
    for edu in missing_education:
        recs.append(MatchRecommendation(
            category="education",
            priority="medium",
            message=f"Acquire or highlight degree requirement: {edu}"
        ))
        
    # Missing certifications -> MEDIUM
    for cert in missing_certifications:
        recs.append(MatchRecommendation(
            category="certifications",
            priority="medium",
            message=f"Consider obtaining certification: {cert}"
        ))
        
    # Missing keywords -> LOW
    for kw in missing_keywords:
        recs.append(MatchRecommendation(
            category="keywords",
            priority="low",
            message=f"Incorporate keyword: {kw}"
        ))
        
    # Remove duplicates preserving order
    seen = set()
    unique_recs = []
    for r in recs:
        key = (r.category, r.priority, r.message.strip().lower())
        if key not in seen:
            seen.add(key)
            unique_recs.append(r)
            
    # Sort: HIGH -> MEDIUM -> LOW
    priority_order = {"high": 0, "medium": 1, "low": 2}
    unique_recs.sort(key=lambda x: priority_order.get(x.priority, 3))
    
    # Limit
    limit = getattr(settings, "JOB_MATCH_MAX_RECOMMENDATIONS", 10)
    return unique_recs[:limit]

