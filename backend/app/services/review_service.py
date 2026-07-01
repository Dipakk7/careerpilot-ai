import json
import uuid
from datetime import datetime
import structlog
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.models.resume import Resume
from app.models.ai_resume_review import AIResumeReview
from app.crud import ai_resume_review as crud
from app.ai.services.ai_service import AIService
from app.ai.providers.factory import AIProviderFactory
from app.ai.config import REVIEW_MODES
from app.services.ats.ats_service import calculate_ats_score

logger = structlog.get_logger()

class ResumeReviewService:
    """Service orchestrating AI Resume Reviews with schema validation, configuration-driven modes, and database caching."""

    def __init__(self, db: Session):
        self.db = db

    async def get_review(self, review_id: uuid.UUID, user_id: uuid.UUID) -> Optional[AIResumeReview]:
        """Fetch a specific review from database by ID and user."""
        return crud.get_review_by_id(self.db, review_id, user_id)

    async def get_reviews_for_resume(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> List[AIResumeReview]:
        """Fetch all reviews for a specific resume."""
        return crud.get_reviews_by_resume_id(self.db, resume_id, user_id)

    async def delete_review(self, review_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a review from database."""
        review = crud.get_review_by_id(self.db, review_id, user_id)
        if not review:
            return False
        return crud.delete_review_record(self.db, review)

    async def review_resume(
        self,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        mode: str = "STANDARD",
        language: str = "en",
        model_override: Optional[str] = None,
        bypass_cache: bool = False
    ) -> AIResumeReview:
        """Orchestrate AI Resume Review generation, database caching, and validation."""
        # 1. Validation
        if not resume_id or not user_id:
            raise ValueError("Missing required identifiers: resume_id and user_id must be provided.")

        # Retrieve resume
        resume = self.db.query(Resume).filter(
            Resume.id == resume_id,
            Resume.user_id == user_id
        ).first()

        if not resume:
            raise ValueError(f"Resume with ID '{resume_id}' not found.")

        # Reject empty resumes or invalid parsed JSON
        if not resume.parsed_data:
            raise ValueError("Resume must be parsed before it can be reviewed.")

        if not isinstance(resume.parsed_data, dict):
            raise ValueError("Invalid parsed JSON format in resume database record.")

        # Unsupported resume versions validation
        parser_version = resume.parsed_data.get("parser_version")
        if parser_version and str(parser_version).startswith("0."):
            raise ValueError(f"Unsupported resume parser version: '{parser_version}'. Version 1.0.0 or higher is required.")

        # Verify review mode is supported
        normalized_mode = mode.upper().strip()
        if normalized_mode not in REVIEW_MODES:
            raise ValueError(f"Unsupported review mode: '{mode}'. Supported: {list(REVIEW_MODES.keys())}")

        mode_config = REVIEW_MODES[normalized_mode]

        # 2. Cache check
        if not bypass_cache:
            existing_reviews = crud.get_reviews_by_resume_id(self.db, resume_id, user_id)
            for rev in existing_reviews:
                meta = rev.review_metadata or {}
                if (
                    meta.get("mode") == normalized_mode
                    and meta.get("language") == language
                    and (model_override is None or rev.model == model_override)
                ):
                    logger.info("reusing_cached_resume_review", review_id=str(rev.id), resume_id=str(resume_id))
                    return rev

        # 3. Calculate/Retrieve ATS score output
        ats_score_response = calculate_ats_score(resume)
        self.db.commit()

        # 4. Initialize specialized AI Provider / Service
        provider = AIProviderFactory.get_provider(model_name=model_override)
        ai_service = AIService(provider)

        # 5. Prepare variables for Jinja prompt rendering
        variables = {
            "mode": normalized_mode,
            "language": language,
            "resume_json": json.dumps(resume.parsed_data, indent=2, default=str),
            "ats_output": ats_score_response.model_dump_json(indent=2)
        }

        # 6. Execute AIService
        logger.info(
            "calling_ai_service_for_resume_review",
            resume_id=str(resume_id),
            mode=normalized_mode,
            model=provider.client.model,
            provider=provider.provider_name
        )

        try:
            structured_response = await ai_service.execute(
                category="resume",
                name="review",
                variables=variables,
                parser_type="json",
                temperature=mode_config["temperature"],
                max_tokens=mode_config["max_tokens"]
            )
        except Exception as e:
            logger.error(
                "resume_review_audit_log",
                provider=provider.provider_name,
                model=provider.client.model,
                prompt_version="1.0.0",
                latency_ms=0.0,
                status="FAILURE",
                error=str(e),
                resume_id=str(resume_id)
            )
            raise

        parsed_review = structured_response.parsed_response
        if not isinstance(parsed_review, dict):
            raise ValueError("AI response parser did not return a valid dictionary.")

        # Ensure essential structure exists or default it
        overall_score = parsed_review.get("overall_score", 0)
        parsed_review["overall_score"] = min(max(overall_score, 0), 100)

        # 7. Audit trail metadata and persistence
        prompt_version = structured_response.prompt_version
        model_used = structured_response.model
        provider_used = structured_response.provider
        latency_ms = structured_response.latency_ms

        review_metadata = {
            "prompt_version": prompt_version,
            "model": model_used,
            "provider": provider_used,
            "latency_ms": latency_ms,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "review_version": "1.0.0",
            "mode": normalized_mode,
            "language": language
        }

        # Save to database
        db_review = crud.create_review(
            db=self.db,
            user_id=user_id,
            resume_id=resume_id,
            review=parsed_review,
            review_metadata=review_metadata,
            provider=provider_used,
            model=model_used,
            prompt_version=prompt_version
        )

        # Audit Trail Logging (Strict privacy: NO raw resume text or prompt text stored in log)
        logger.info(
            "resume_review_audit_log",
            provider=provider_used,
            model=model_used,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
            status="SUCCESS",
            review_id=str(db_review.id),
            resume_id=str(resume_id)
        )

        return db_review
