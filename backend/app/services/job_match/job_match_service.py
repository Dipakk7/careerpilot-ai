from typing import TYPE_CHECKING
from datetime import datetime, timezone
import structlog

from app.schemas.job_match import JobMatchResponse
from app.schemas.job_gap import GapAnalysisResponse
from app.core.ats_constants import ATS_VERSION
from app.core.job_match_constants import JOB_MATCH_VERSION, MATCH_GRADES
from app.core.config import settings
from app.services.job_match.matcher import (
    match_skills,
    match_experience,
    match_education,
    match_certifications,
    match_keywords
)
from app.services.job_match.gap_analysis import (
    analyze_skill_gaps,
    analyze_experience_gap,
    analyze_education_gap,
    analyze_certification_gap,
    analyze_keyword_gap
)
from app.services.job_match.prioritizer import prioritize_gaps
from app.services.job_match.analyzer import (
    calculate_match_breakdown,
    calculate_match_score
)
from app.services.job_match.recommendations import generate_job_recommendations
from app.services.job_match.parser import extract_keywords

if TYPE_CHECKING:
    from app.models.resume import Resume
    from app.schemas.job_match import JobDescription

logger = structlog.get_logger()

def calculate_job_match(
    resume: "Resume",
    job_description: "JobDescription"
) -> JobMatchResponse:
    """
    Calculate the match score, grade, breakdown, matched/missing/extra skills,
    and recommendations for a resume against a job description.
    """
    logger.info("job_match_started", resume_id=str(resume.id) if resume else None)
    
    try:
        # 1. Validate resume parsed_data exists
        if not resume or not resume.id:
            raise ValueError("Invalid resume model provided")
            
        if not resume.parsed_data or "data" not in resume.parsed_data:
            raise ValueError("Resume has not been parsed or parsed_data is empty")
            
        # 2. Validate job description
        if not job_description:
            raise ValueError("Job description is missing")
            
        if not hasattr(job_description, "required_skills") or job_description.required_skills is None:
            raise ValueError("Job description is invalid: missing required_skills")

        # Extract resume fields from parsed_data
        data = resume.parsed_data.get("data", {})
        
        def _get_list(field_key: str) -> list:
            node = data.get(field_key, {})
            if isinstance(node, dict):
                return node.get("value", [])
            elif isinstance(node, list):
                return node
            elif hasattr(node, "value"):
                return getattr(node, "value", [])
            return []

        resume_skills = _get_list("skills")
        resume_experience = _get_list("experience")
        resume_education = _get_list("education")
        resume_certifications = _get_list("certifications")

        # 3. Run match_skills
        skills_match = match_skills(
            resume_skills=resume_skills,
            required_skills=job_description.required_skills,
            preferred_skills=job_description.preferred_skills
        )
        logger.info(
            "job_match_skills",
            resume_id=str(resume.id),
            matched_req_count=len(skills_match["matched_required"]),
            missing_req_count=len(skills_match["missing_required"]),
            matched_pref_count=len(skills_match["matched_preferred"]),
            missing_pref_count=len(skills_match["missing_preferred"]),
            extra_count=len(skills_match["extra_skills"])
        )

        # 4. Run match_experience
        experience_match = match_experience(
            resume_experience=resume_experience,
            job_experience=job_description.experience
        )
        logger.info(
            "job_match_experience",
            resume_id=str(resume.id),
            matched=experience_match["matched"],
            experience_score=experience_match["experience_score"]
        )

        # 5. Run match_education
        education_match = match_education(
            resume_education=resume_education,
            job_education=job_description.education
        )

        # 6. Run match_certifications
        certifications_match = match_certifications(
            resume_certifications=resume_certifications,
            job_certifications=job_description.certifications
        )

        # 7. Run match_keywords
        resume_edu_degrees = [e.get("degree", "") for e in resume_education if isinstance(e, dict) and e.get("degree")]
        resume_exp_desc = [e.get("description", "") for e in resume_experience if isinstance(e, dict) and e.get("description")]
        
        resume_keywords = extract_keywords(
            text=resume.raw_text,
            skills=resume_skills,
            education=resume_edu_degrees,
            certifications=resume_certifications,
            experience=resume_exp_desc
        )
        
        keywords_match = match_keywords(
            resume_keywords=resume_keywords,
            job_keywords=job_description.keywords
        )

        # 8. Calculate breakdown
        breakdown = calculate_match_breakdown(
            skills_score=skills_match["score"],
            experience_score=experience_match["experience_score"],
            education_score=education_match["score"],
            certifications_score=certifications_match["score"],
            keywords_score=keywords_match["keyword_score"]
        )

        # 9. Calculate overall score
        overall_score = calculate_match_score(breakdown)

        # 10. Determine grade
        def determine_match_grade(score: int) -> str:
            sorted_grades = sorted(MATCH_GRADES.items(), key=lambda x: x[1], reverse=True)
            for gr, threshold in sorted_grades:
                if score >= threshold:
                    return gr
            return "Poor"
            
        grade = determine_match_grade(overall_score)
        logger.info(
            "job_match_score",
            resume_id=str(resume.id),
            overall_score=overall_score,
            grade=grade
        )

        # 11. Generate recommendations
        recs = generate_job_recommendations(
            missing_skills=skills_match["missing_required"],
            missing_education=education_match["missing"],
            missing_certifications=certifications_match["missing"],
            missing_experience=experience_match["missing"],
            missing_keywords=keywords_match["missing_keywords"],
            missing_preferred_skills=skills_match["missing_preferred"]
        )

        # 12. Return JobMatchResponse
        response = JobMatchResponse(
            resume_id=resume.id,
            match_score=overall_score,
            grade=grade,
            breakdown=breakdown,
            matched_skills=sorted(skills_match["matched_required"] + skills_match["matched_preferred"]),
            missing_skills=sorted(skills_match["missing_required"] + skills_match["missing_preferred"]),
            extra_skills=sorted(skills_match["extra_skills"]),
            recommendations=recs,
            parser_version=resume.parsed_data.get("parser_version", settings.PARSER_VERSION),
            ats_version=ATS_VERSION,
            job_match_version=JOB_MATCH_VERSION,
            generated_at=datetime.now(timezone.utc)
        )
        
        logger.info("job_match_completed", resume_id=str(resume.id))
        return response

    except Exception as e:
        logger.error("job_match_failed", resume_id=str(resume.id) if (resume and hasattr(resume, 'id') and resume.id) else "unknown", error=str(e))
        raise e


def analyze_resume_gap(
    resume: "Resume",
    job_description: "JobDescription"
) -> GapAnalysisResponse:
    """
    Run the Explainable Gap Analysis Engine on a resume against a job description.
    """
    logger.info("gap_analysis_started", resume_id=str(resume.id) if resume else None)
    
    try:
        # 1. Validate resume parsed_data exists
        if not resume or not resume.id:
            raise ValueError("Invalid resume model provided")
            
        if not resume.parsed_data or "data" not in resume.parsed_data:
            raise ValueError("Resume has not been parsed or parsed_data is empty")
            
        # 2. Validate job description
        if not job_description:
            raise ValueError("Job description is missing")
            
        if not hasattr(job_description, "required_skills") or job_description.required_skills is None:
            raise ValueError("Job description is invalid: missing required_skills")

        # Extract resume fields from parsed_data
        data = resume.parsed_data.get("data", {})
        
        def _get_list(field_key: str) -> list:
            node = data.get(field_key, {})
            if isinstance(node, dict):
                return node.get("value", [])
            elif isinstance(node, list):
                return node
            elif hasattr(node, "value"):
                return getattr(node, "value", [])
            return []

        resume_skills = _get_list("skills")
        resume_experience = _get_list("experience")
        resume_education = _get_list("education")
        resume_certifications = _get_list("certifications")

        # Extract keywords using same logic as matching
        resume_edu_degrees = [e.get("degree", "") for e in resume_education if isinstance(e, dict) and e.get("degree")]
        resume_exp_desc = [e.get("description", "") for e in resume_experience if isinstance(e, dict) and e.get("description")]
        
        resume_keywords = extract_keywords(
            text=resume.raw_text,
            skills=resume_skills,
            education=resume_edu_degrees,
            certifications=resume_certifications,
            experience=resume_exp_desc
        )

        # 3. Perform gap analyses
        skill_gap_dict = analyze_skill_gaps(
            resume_skills=resume_skills,
            required_skills=job_description.required_skills,
            preferred_skills=job_description.preferred_skills
        )
        
        experience_gap_dict = analyze_experience_gap(
            resume_experience=resume_experience,
            job_experience=job_description.experience
        )
        
        education_gap_dict = analyze_education_gap(
            resume_education=resume_education,
            job_education=job_description.education
        )
        
        certification_gap_dict = analyze_certification_gap(
            resume_certifications=resume_certifications,
            job_certifications=job_description.certifications
        )
        
        keyword_gap_dict = analyze_keyword_gap(
            resume_keywords=resume_keywords,
            job_keywords=job_description.keywords
        )
        
        # 4. Generate prioritized improvements
        priority_improvements = prioritize_gaps(
            skill_gap=skill_gap_dict,
            experience_gap=experience_gap_dict,
            education_gap=education_gap_dict,
            certification_gap=certification_gap_dict,
            keyword_gap=keyword_gap_dict,
            resume=resume
        )
        
        # 5. Determine overall_match status
        # overall_match is true if all core requirements (required skills, experience, education) are matched
        overall_match = (
            len(skill_gap_dict.get("missing_required", [])) == 0 and
            experience_gap_dict.get("matched", True) and
            education_gap_dict.get("matched", True)
        )
        
        response = GapAnalysisResponse(
            resume_id=resume.id,
            overall_match=overall_match,
            skill_gap=skill_gap_dict,
            experience_gap=experience_gap_dict,
            education_gap=education_gap_dict,
            certification_gap=certification_gap_dict,
            keyword_gap=keyword_gap_dict,
            priority_improvements=priority_improvements,
            analysis_version=JOB_MATCH_VERSION,
            analyzed_at=datetime.now(timezone.utc)
        )
        
        logger.info(
            "gap_analysis_completed",
            resume_id=str(resume.id),
            overall_match=overall_match
        )
        return response

    except Exception as e:
        logger.error(
            "gap_analysis_failed",
            resume_id=str(resume.id) if (resume and hasattr(resume, "id") and resume.id) else "unknown",
            error=str(e)
        )
        raise e


