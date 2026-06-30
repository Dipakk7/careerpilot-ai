from typing import TYPE_CHECKING
from datetime import datetime, timezone

from app.core.ats_constants import ATS_VERSION
from app.schemas.ats import ATSScoreResponse, ATSBreakdown
from app.services.ats.scoring import (
    score_contact,
    score_skills,
    score_education,
    score_experience,
    score_projects,
    score_certifications,
)
from app.services.ats.grading import determine_grade, generate_grade_summary
from app.services.ats.recommendations import (
    generate_strengths,
    generate_weaknesses,
    generate_recommendations,
)

if TYPE_CHECKING:
    from app.models.resume import Resume

def calculate_ats_score(resume: "Resume") -> "ATSScoreResponse":
    """
    Full orchestration: runs all scoring functions,
    generates recommendations, builds response.
    Will include parser_version (from resume.parsed_data
    metadata if available, else 'unknown') and
    ats_version (from ATS_VERSION constant).
    """
    parsed_data = resume.parsed_data or {}
    
    # Run all scoring functions
    contact_val = score_contact(parsed_data)
    skills_val = score_skills(parsed_data)
    education_val = score_education(parsed_data)
    experience_val = score_experience(parsed_data)
    projects_val = score_projects(parsed_data)
    certifications_val = score_certifications(parsed_data)
    
    # Calculate total
    overall_score = (
        contact_val
        + skills_val
        + education_val
        + experience_val
        + projects_val
        + certifications_val
    )
    # Ensure overall score is capped at 100 and non-negative
    overall_score = min(max(overall_score, 0), 100)
    
    # Determine grade
    grade = determine_grade(overall_score)
    
    # Update resume object
    resume.ats_score = overall_score
    
    # Create breakdown
    breakdown = ATSBreakdown(
        contact=contact_val,
        skills=skills_val,
        education=education_val,
        experience=experience_val,
        projects=projects_val,
        certifications=certifications_val,
    )
    
    # Get parser version
    parser_version = parsed_data.get("parser_version", "unknown") if parsed_data else "unknown"
    
    # Generate recommendations components
    strengths = generate_strengths(parsed_data, breakdown)
    weaknesses = generate_weaknesses(parsed_data, breakdown)
    recommendations = generate_recommendations(parsed_data, breakdown)
    
    # Generate grade summary
    grade_summary = generate_grade_summary(grade)
    
    # Build and return response
    return ATSScoreResponse(
        resume_id=resume.id,
        overall_score=overall_score,
        grade=grade,
        grade_summary=grade_summary,
        breakdown=breakdown,
        strengths=strengths,
        weaknesses=weaknesses,
        recommendations=recommendations,
        parser_version=parser_version,
        ats_version=ATS_VERSION,
        scored_at=datetime.now(timezone.utc),
    )
