import json
import uuid
import structlog
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from pydantic import BaseModel, ValidationError

from app.models.resume import Resume
from app.models.ai_resume_optimization import AIResumeOptimization
from app.crud import ai_resume_optimization as crud
from app.ai.services.ai_service import AIService
from app.ai.providers.factory import AIProviderFactory
from app.ai.config import OPTIMIZATION_MODES
from app.ai.exceptions import ResponseParsingError
from app.services.ats.ats_service import calculate_ats_score
from app.services.job_match.parser import parse_job_description
from app.services.job_match.job_match_service import calculate_job_match, analyze_resume_gap

from app.schemas.ai_resume_optimization import (
    ResumeQualityScore,
    MissingSkillDetail,
    ATSOptimizationDetail,
    KeywordAnalysis,
    AchievementOptimizationDetail,
    ResumeCompleteness,
    CareerReadiness,
    IndustryAlignmentDetail,
    OptimizationRecommendation,
)

logger = structlog.get_logger()

class LLMOptimizationOutput(BaseModel):
    quality_score: ResumeQualityScore
    missing_skills: List[MissingSkillDetail]
    ats_optimization: ATSOptimizationDetail
    keyword_optimization: KeywordAnalysis
    achievement_optimization: List[AchievementOptimizationDetail]
    completeness: ResumeCompleteness
    career_readiness: CareerReadiness
    industry_alignment: List[IndustryAlignmentDetail]
    recommendations: List[OptimizationRecommendation]

class ResumeOptimizationService:
    """Service orchestrating AI Resume Optimization & Intelligence Engine."""

    def __init__(self, db: Session):
        self.db = db

    async def get_optimization(self, optimization_id: uuid.UUID, user_id: uuid.UUID) -> Optional[AIResumeOptimization]:
        """Fetch a specific optimization from database by ID and user."""
        return crud.get_optimization_by_id(self.db, optimization_id, user_id)

    async def get_optimizations_for_resume(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> List[AIResumeOptimization]:
        """Fetch all optimizations for a specific resume."""
        return crud.get_optimizations_by_resume_id(self.db, resume_id, user_id)

    async def delete_optimization(self, optimization_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete an optimization from database."""
        opt = crud.get_optimization_by_id(self.db, optimization_id, user_id)
        if not opt:
            return False
        return crud.delete_optimization_record(self.db, opt)

    async def optimize_resume(
        self,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        job_description: Optional[str] = None,
        mode: str = "STANDARD",
        model_override: Optional[str] = None,
        bypass_cache: bool = False
    ) -> AIResumeOptimization:
        """Orchestrate optimization flow combining ATS, Job Match, Skill Gap and LLM intelligence."""
        # 1. Validation
        if not resume_id or not user_id:
            raise ValueError("Missing required identifiers: resume_id and user_id must be provided.")

        resume = self.db.query(Resume).filter(
            Resume.id == resume_id,
            Resume.user_id == user_id
        ).first()

        if not resume:
            raise ValueError(f"Resume with ID '{resume_id}' not found.")

        # Reject empty resumes or invalid parsed JSON
        if not resume.parsed_data or not isinstance(resume.parsed_data, dict):
            raise ValueError("Resume must be parsed before it can be optimized.")

        # Unsupported resume versions validation
        parser_version = resume.parsed_data.get("parser_version")
        if parser_version and str(parser_version).startswith("0."):
            raise ValueError(f"Unsupported resume parser version: '{parser_version}'. Version 1.0.0 or higher is required.")

        # Verify optimization mode is supported
        normalized_mode = mode.upper().strip()
        if normalized_mode not in OPTIMIZATION_MODES:
            raise ValueError(f"Unsupported optimization mode: '{mode}'. Supported: {list(OPTIMIZATION_MODES.keys())}")

        mode_config = OPTIMIZATION_MODES[normalized_mode]

        # 2. Database Cache Check
        if not bypass_cache:
            existing = crud.get_optimizations_by_resume_id(self.db, resume_id, user_id)
            for opt in existing:
                meta = opt.optimization_metadata or {}
                # Check matching attributes to reuse cached run
                if (
                    meta.get("mode") == normalized_mode
                    and meta.get("job_description") == job_description
                    and (model_override is None or opt.model == model_override)
                ):
                    logger.info("reusing_cached_resume_optimization", optimization_id=str(opt.id), resume_id=str(resume_id))
                    return opt

        # 3. Calculate python-based ATS Score
        ats_score_response = calculate_ats_score(resume)
        self.db.commit()

        # 4. If target job description is provided, calculate match and gaps
        job_match_response = None
        gap_analysis_response = None

        if job_description and job_description.strip():
            try:
                job_desc_model = parse_job_description(job_description)
                job_match_response = calculate_job_match(resume, job_desc_model)
                gap_analysis_response = analyze_resume_gap(resume, job_desc_model)
            except Exception as e:
                logger.warning("failed_calculating_optional_job_match_insights", error=str(e))

        # 5. Initialize active AI Provider and service
        provider = AIProviderFactory.get_provider(model_name=model_override)
        ai_service = AIService(provider)

        # 6. Prepare Jinja template variables
        variables = {
            "mode": normalized_mode,
            "resume_json": json.dumps(resume.parsed_data, indent=2, default=str),
            "ats_output": ats_score_response.model_dump_json(indent=2),
            "job_match_output": job_match_response.model_dump_json(indent=2) if job_match_response else "",
            "gap_analysis_output": gap_analysis_response.model_dump_json(indent=2) if gap_analysis_response else "",
            "job_description": job_description or ""
        }

        # 7. Execute AI optimization with schema verification and retry-once
        attempts = 2
        parsed_response = None
        structured_response = None

        for attempt in range(attempts):
            try:
                logger.info(
                    "calling_ai_service_for_resume_optimization",
                    resume_id=str(resume_id),
                    mode=normalized_mode,
                    attempt=attempt + 1,
                    has_jd=bool(job_description)
                )
                structured_response = await ai_service.execute(
                    category="resume",
                    name="optimization",
                    variables=variables,
                    parser_type="json",
                    temperature=mode_config["temperature"],
                    max_tokens=mode_config["max_tokens"]
                )
                parsed_response = structured_response.parsed_response
                if not isinstance(parsed_response, dict):
                    raise ValueError("AI response parser did not return a valid dictionary.")

                # Enforce structured validation against output schema
                LLMOptimizationOutput.model_validate(parsed_response)
                break
            except (ResponseParsingError, ValidationError, ValueError, Exception) as e:
                logger.warning(
                    "ai_resume_optimization_validation_failed",
                    attempt=attempt + 1,
                    error=str(e)
                )
                if attempt == attempts - 1:
                    # Final attempt failed
                    logger.error(
                        "resume_optimization_audit_log",
                        provider=provider.provider_name,
                        model=provider.client.model,
                        prompt_version="1.0.0",
                        latency_ms=0.0,
                        status="FAILURE",
                        error=str(e),
                        resume_id=str(resume_id)
                    )
                    raise ValueError(f"AI returned malformed output or failed validation: {str(e)}")

        prompt_version = structured_response.prompt_version
        model_used = structured_response.model
        provider_used = structured_response.provider
        latency_ms = structured_response.latency_ms

        optimization_metadata = {
            "prompt_version": prompt_version,
            "model": model_used,
            "provider": provider_used,
            "latency_ms": latency_ms,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "mode": normalized_mode,
            "job_description": job_description
        }

        # Extracted score payload
        quality_score_payload = parsed_response.get("quality_score", {})

        # Save record to database
        db_opt = crud.create_optimization(
            db=self.db,
            user_id=user_id,
            resume_id=resume_id,
            workflow_result=None,  # workflow service overrides this
            optimization_result=parsed_response,
            quality_score=quality_score_payload,
            provider=provider_used,
            model=model_used,
            prompt_version=prompt_version,
            optimization_metadata=optimization_metadata
        )

        # Audit trace logging - NEVER log PII details (prompt, resume text, job desc)
        logger.info(
            "resume_optimization_audit_log",
            provider=provider_used,
            model=model_used,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
            status="SUCCESS",
            optimization_id=str(db_opt.id),
            resume_id=str(resume_id)
        )

        return db_opt
