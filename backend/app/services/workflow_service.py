import uuid
import structlog
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.resume import Resume
from app.core.enums import ResumeStatus
from app.services.parser.parser_service import parse_resume
from app.services.review_service import ResumeReviewService
from app.services.rewrite_service import ResumeRewriteService
from app.services.optimization_service import ResumeOptimizationService
from app.schemas.ai_resume_optimization import ResumeWorkflowResponse

logger = structlog.get_logger()

class ResumeWorkflowService:
    """AI Workflow Orchestrator implementing Parser -> Review -> Rewrite -> Optimization pipeline."""

    def __init__(self, db: Session):
        self.db = db

    async def execute_workflow(
        self,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        job_description: Optional[str] = None,
        mode: str = "STANDARD",
        model_override: Optional[str] = None,
        bypass_cache: bool = False
    ) -> ResumeWorkflowResponse:
        """Execute the full resume AI workflow pipeline in sequence."""
        stages = {
            "parser": "PENDING",
            "review": "PENDING",
            "rewrite": "PENDING",
            "optimization": "PENDING"
        }
        
        logger.info(
            "ai_workflow_pipeline_started",
            resume_id=str(resume_id),
            user_id=str(user_id),
            mode=mode,
            has_jd=bool(job_description)
        )

        # 1. Fetch and validate resume existence
        resume = self.db.query(Resume).filter(
            Resume.id == resume_id,
            Resume.user_id == user_id
        ).first()

        if not resume:
            raise ValueError(f"Resume with ID '{resume_id}' not found.")

        review_id = None
        rewrite_id = None
        optimization_id = None
        quality_score = None

        try:
            # 2. Stage 1: Parser
            if resume.status != ResumeStatus.PARSED:
                logger.info("workflow_stage_parser_starting", resume_id=str(resume_id))
                try:
                    parse_resume(self.db, resume_id)
                    # Reload resume to get fresh parsed_data
                    self.db.refresh(resume)
                    stages["parser"] = "SUCCESS"
                except Exception as parse_err:
                    stages["parser"] = "FAILED"
                    logger.error("workflow_stage_parser_failed", resume_id=str(resume_id), error=str(parse_err))
                    raise ValueError(f"Resume parsing stage failed: {str(parse_err)}")
            else:
                stages["parser"] = "SUCCESS"

            # Re-verify parsed data integrity
            if not resume.parsed_data or not isinstance(resume.parsed_data, dict):
                raise ValueError("Resume must be successfully parsed to execute workflow stages.")

            parser_version = resume.parsed_data.get("parser_version")
            if parser_version and str(parser_version).startswith("0."):
                raise ValueError(f"Unsupported resume parser version: '{parser_version}'. Version 1.0.0 or higher is required.")

            # 3. Stage 2: Resume Review
            logger.info("workflow_stage_review_starting", resume_id=str(resume_id))
            try:
                review_service = ResumeReviewService(self.db)
                # Map standardized mode for Review Mode
                review_mode = "STANDARD"
                if mode.upper() in ["BASIC", "FAST"]:
                    review_mode = "FAST"
                elif mode.upper() in ["PROFESSIONAL", "ADVANCED", "DETAILED"]:
                    review_mode = "DETAILED"

                db_review = await review_service.review_resume(
                    resume_id=resume_id,
                    user_id=user_id,
                    mode=review_mode,
                    model_override=model_override,
                    bypass_cache=bypass_cache
                )
                review_id = db_review.id
                stages["review"] = "SUCCESS"
            except Exception as review_err:
                stages["review"] = "FAILED"
                logger.error("workflow_stage_review_failed", resume_id=str(resume_id), error=str(review_err))
                raise ValueError(f"Resume review stage failed: {str(review_err)}")

            # 4. Stage 3: Resume Rewrite
            logger.info("workflow_stage_rewrite_starting", resume_id=str(resume_id))
            try:
                rewrite_service = ResumeRewriteService(self.db)
                rewrite_mode = "STANDARD"
                if mode.upper() == "PROFESSIONAL":
                    rewrite_mode = "PROFESSIONAL"
                elif mode.upper() == "BASIC":
                    rewrite_mode = "CONCISE"

                db_rewrite = await rewrite_service.rewrite_resume(
                    resume_id=resume_id,
                    user_id=user_id,
                    mode=rewrite_mode,
                    job_description=job_description,
                    model_override=model_override,
                    bypass_cache=bypass_cache
                )
                rewrite_id = db_rewrite.id
                stages["rewrite"] = "SUCCESS"
            except Exception as rewrite_err:
                stages["rewrite"] = "FAILED"
                logger.error("workflow_stage_rewrite_failed", resume_id=str(resume_id), error=str(rewrite_err))
                raise ValueError(f"Resume rewrite stage failed: {str(rewrite_err)}")

            # 5. Stage 4: Resume Optimization
            logger.info("workflow_stage_optimization_starting", resume_id=str(resume_id))
            try:
                optimization_service = ResumeOptimizationService(self.db)
                db_opt = await optimization_service.optimize_resume(
                    resume_id=resume_id,
                    user_id=user_id,
                    job_description=job_description,
                    mode=mode,
                    model_override=model_override,
                    bypass_cache=bypass_cache
                )
                optimization_id = db_opt.id
                quality_score = db_opt.quality_score.get("overall_score", 0)
                stages["optimization"] = "SUCCESS"

                # Update workflow execution result summary on optimization DB row
                workflow_summary = {
                    "stages": stages,
                    "review_id": str(review_id),
                    "rewrite_id": str(rewrite_id),
                    "optimization_id": str(optimization_id),
                    "completed_at": datetime.utcnow().isoformat() + "Z"
                }
                db_opt.workflow_result = workflow_summary
                self.db.commit()

            except Exception as opt_err:
                stages["optimization"] = "FAILED"
                logger.error("workflow_stage_optimization_failed", resume_id=str(resume_id), error=str(opt_err))
                raise ValueError(f"Resume optimization stage failed: {str(opt_err)}")

        except Exception as e:
            logger.error("ai_workflow_pipeline_failed", resume_id=str(resume_id), stages=stages, error=str(e))
            raise

        logger.info(
            "ai_workflow_pipeline_completed",
            resume_id=str(resume_id),
            optimization_id=str(optimization_id),
            quality_score=quality_score
        )

        return ResumeWorkflowResponse(
            resume_id=resume_id,
            stages=stages,
            quality_score=quality_score,
            optimization_id=optimization_id,
            review_id=review_id,
            rewrite_id=rewrite_id,
            created_at=datetime.utcnow()
        )
