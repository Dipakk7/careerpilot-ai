import json
import uuid
from datetime import datetime
import structlog
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from pydantic import BaseModel, ValidationError

from app.models.resume import Resume
from app.models.ai_resume_rewrite import AIResumeRewrite
from app.crud import ai_resume_rewrite as crud
from app.ai.services.ai_service import AIService
from app.ai.providers.factory import AIProviderFactory
from app.ai.config import REWRITE_MODES
from app.utils.diff_engine import compute_diff
from app.schemas.ai_resume_rewrite import ChangeTracking, RewriteQualityScore, KeywordOptimization
from app.ai.exceptions import ResponseParsingError

logger = structlog.get_logger()

# Pydantic schema for structured LLM response validation
class LLMRewriteOutput(BaseModel):
    rewritten_content: dict
    change_tracking: Dict[str, ChangeTracking]
    quality_scores: RewriteQualityScore
    keyword_optimization: Optional[KeywordOptimization] = None

class ResumeRewriteService:
    """Service orchestrating AI Resume Rewrites with structured output, fact preservation, diff engine, and undo support."""

    def __init__(self, db: Session):
        self.db = db

    async def get_rewrite(self, rewrite_id: uuid.UUID, user_id: uuid.UUID) -> Optional[AIResumeRewrite]:
        """Fetch a specific rewrite from database by ID and user."""
        return crud.get_rewrite_by_id(self.db, rewrite_id, user_id)

    async def get_rewrites_for_resume(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> List[AIResumeRewrite]:
        """Fetch all rewrites for a specific resume."""
        return crud.get_rewrites_by_resume_id(self.db, resume_id, user_id)

    async def delete_rewrite(self, rewrite_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a rewrite record from database."""
        rewrite = crud.get_rewrite_by_id(self.db, rewrite_id, user_id)
        if not rewrite:
            return False
        return crud.delete_rewrite_record(self.db, rewrite)

    async def rollback_rewrite(self, rewrite_id: uuid.UUID, user_id: uuid.UUID) -> Dict[str, Any]:
        """Rollback the resume parsed_data to the original_content state prior to this rewrite."""
        rewrite = crud.get_rewrite_by_id(self.db, rewrite_id, user_id)
        if not rewrite:
            raise ValueError(f"Rewrite record '{rewrite_id}' not found.")

        resume = self.db.query(Resume).filter(
            Resume.id == rewrite.resume_id,
            Resume.user_id == user_id
        ).first()

        if not resume:
            raise ValueError(f"Associated resume not found.")

        # Revert the resume parsed_data
        resume.parsed_data = rewrite.original_content
        resume.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(
            "resume_rewrite_rollback_applied",
            rewrite_id=str(rewrite_id),
            resume_id=str(resume.id),
            user_id=str(user_id)
        )

        return {
            "success": True,
            "message": "Resume rolled back successfully.",
            "rolled_back_to_id": rewrite.parent_id,
            "resume_id": resume.id
        }

    async def rewrite_resume(
        self,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        mode: str = "STANDARD",
        section_name: Optional[str] = None,
        job_description: Optional[str] = None,
        model_override: Optional[str] = None,
        bypass_cache: bool = False
    ) -> AIResumeRewrite:
        """Orchestrate AI Resume Rewrite generation, validation, change tracking, and database persistence."""
        # 1. Validation
        if not resume_id or not user_id:
            raise ValueError("Missing required identifiers: resume_id and user_id must be provided.")

        resume = self.db.query(Resume).filter(
            Resume.id == resume_id,
            Resume.user_id == user_id
        ).first()

        if not resume:
            raise ValueError(f"Resume with ID '{resume_id}' not found.")

        if not resume.parsed_data:
            raise ValueError("Resume must be parsed before it can be rewritten.")

        if not isinstance(resume.parsed_data, dict):
            raise ValueError("Invalid parsed JSON format in resume database record.")

        parser_version = resume.parsed_data.get("parser_version")
        if parser_version and str(parser_version).startswith("0."):
            raise ValueError(f"Unsupported resume parser version: '{parser_version}'. Version 1.0.0 or higher is required.")

        normalized_mode = mode.upper().strip()
        if normalized_mode not in REWRITE_MODES:
            raise ValueError(f"Unsupported rewrite mode: '{mode}'. Supported: {list(REWRITE_MODES.keys())}")

        mode_config = REWRITE_MODES[normalized_mode]

        # Valid Section validation if section_name is provided
        valid_sections = {
            "summary", "professional_summary",
            "experience", "work_experience",
            "projects",
            "skills",
            "education",
            "certifications",
            "achievements",
            "career_objective"
        }

        if section_name:
            normalized_sec = section_name.lower().strip()
            if normalized_sec not in valid_sections:
                raise ValueError(f"Unsupported section name: '{section_name}'.")

        # 2. Database Cache Check
        if not bypass_cache:
            existing = crud.get_rewrites_by_resume_id(self.db, resume_id, user_id)
            for r in existing:
                meta = r.rewrite_metadata or {}
                if (
                    r.rewrite_mode == normalized_mode
                    and r.job_description == job_description
                    and meta.get("section_name") == section_name
                    and (model_override is None or r.model == model_override)
                ):
                    logger.info("reusing_cached_resume_rewrite", rewrite_id=str(r.id), resume_id=str(resume_id))
                    return r

        # 3. Initialize AI Provider / Service
        provider = AIProviderFactory.get_provider(model_name=model_override)
        ai_service = AIService(provider)

        # 4. Prepare variables for Jinja prompt rendering
        variables = {
            "mode": normalized_mode,
            "resume_json": json.dumps(resume.parsed_data, indent=2, default=str),
            "job_description": job_description or "",
            "section_name": section_name or ""
        }

        # 5. Execute AIService with Retry logic (Retry once if invalid JSON/Pydantic validation failure)
        attempts = 2
        parsed_rewrite = None
        structured_response = None

        for attempt in range(attempts):
            try:
                logger.info(
                    "calling_ai_service_for_resume_rewrite",
                    resume_id=str(resume_id),
                    mode=normalized_mode,
                    attempt=attempt + 1,
                    section_name=section_name
                )
                structured_response = await ai_service.execute(
                    category="resume",
                    name="rewrite",
                    variables=variables,
                    parser_type="json",
                    temperature=mode_config["temperature"],
                    max_tokens=mode_config["max_tokens"]
                )
                parsed_rewrite = structured_response.parsed_response

                if not isinstance(parsed_rewrite, dict):
                    raise ValueError("AI response parser did not return a valid dictionary.")

                # Validate with Pydantic schema
                LLMRewriteOutput.model_validate(parsed_rewrite)
                break

            except (ResponseParsingError, ValidationError, ValueError, Exception) as e:
                logger.warning(
                    "ai_resume_rewrite_validation_failed",
                    attempt=attempt + 1,
                    error=str(e)
                )
                if attempt == attempts - 1:
                    # Final attempt failed, audit fail and raise
                    logger.error(
                        "resume_rewrite_audit_log",
                        provider=provider.provider_name,
                        model=provider.client.model,
                        prompt_version="1.0.0",
                        latency_ms=0.0,
                        status="FAILURE",
                        error=str(e),
                        resume_id=str(resume_id)
                    )
                    raise ValueError(f"AI returned malformed output or failed validation: {str(e)}")

        # 6. Apply python diff engine to all change tracking sections
        for key, tracking in parsed_rewrite.get("change_tracking", {}).items():
            orig = tracking.get("original", "")
            rewr = tracking.get("rewritten", "")
            tracking["diff"] = compute_diff(orig, rewr)

        # 7. Merge rewritten content back to create the full rewritten resume JSON
        # If it was a section rewrite, merge only the rewritten section into a copy of original parsed_data
        original_parsed_data = dict(resume.parsed_data)
        rewritten_resume_data = dict(resume.parsed_data)

        llm_rewritten_content = parsed_rewrite.get("rewritten_content", {})

        if section_name:
            # Map normalized section_name back to keys in parsed_data
            target_key = None
            for k in original_parsed_data.keys():
                if k.lower().replace("_", "").strip() == section_name.lower().replace("_", "").strip():
                    target_key = k
                    break
            
            if target_key:
                # Get rewritten value from LLM (keys can match target_key or normalized key)
                rewrite_val = None
                for lk, lv in llm_rewritten_content.items():
                    if lk.lower().replace("_", "").strip() == section_name.lower().replace("_", "").strip():
                        rewrite_val = lv
                        break
                
                if rewrite_val is not None:
                    rewritten_resume_data[target_key] = rewrite_val
            else:
                # If target key not found, try inserting or defaulting
                rewritten_resume_data[section_name] = list(llm_rewritten_content.values())[0] if llm_rewritten_content else ""
        else:
            # Full rewrite, update keys returned by LLM
            for k, v in llm_rewritten_content.items():
                # Find matching key in original parsed data case-insensitively
                match_k = None
                for orig_k in original_parsed_data.keys():
                    if orig_k.lower().replace("_", "").strip() == k.lower().replace("_", "").strip():
                        match_k = orig_k
                        break
                if match_k:
                    rewritten_resume_data[match_k] = v
                else:
                    rewritten_resume_data[k] = v

        # 8. Detect parent version from database for history rollback chain
        latest_rewrite = self.db.query(AIResumeRewrite).filter(
            AIResumeRewrite.resume_id == resume_id,
            AIResumeRewrite.user_id == user_id
        ).order_by(AIResumeRewrite.created_at.desc()).first()
        parent_id = latest_rewrite.id if latest_rewrite else None

        # 9. Persist the rewrite and update the Resume model
        prompt_version = structured_response.prompt_version
        model_used = structured_response.model
        provider_used = structured_response.provider
        latency_ms = structured_response.latency_ms

        rewrite_metadata = {
            "prompt_version": prompt_version,
            "model": model_used,
            "provider": provider_used,
            "latency_ms": latency_ms,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "mode": normalized_mode,
            "section_name": section_name,
            "change_tracking": parsed_rewrite.get("change_tracking", {}),
            "quality_scores": parsed_rewrite.get("quality_scores", {}),
            "keyword_optimization": parsed_rewrite.get("keyword_optimization", {})
        }

        # Save to database
        db_rewrite = crud.create_rewrite(
            db=self.db,
            user_id=user_id,
            resume_id=resume_id,
            parent_id=parent_id,
            original_content=original_parsed_data,
            rewritten_content=rewritten_resume_data,
            rewrite_mode=normalized_mode,
            job_description=job_description,
            provider=provider_used,
            model=model_used,
            prompt_version=prompt_version,
            rewrite_metadata=rewrite_metadata
        )

        # Update resume parsed_data to active rewritten state
        resume.parsed_data = rewritten_resume_data
        resume.updated_at = datetime.utcnow()
        self.db.commit()

        # Audit Trail Logging (Strict privacy: NO raw resume, prompt, or Job Description in log)
        logger.info(
            "resume_rewrite_audit_log",
            provider=provider_used,
            model=model_used,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
            status="SUCCESS",
            rewrite_id=str(db_rewrite.id),
            resume_id=str(resume_id),
            mode=normalized_mode,
            section_name=section_name
        )

        return db_rewrite
