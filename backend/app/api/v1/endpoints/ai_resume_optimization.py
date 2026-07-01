import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import structlog

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.ai_resume_optimization import AIResumeOptimization
from app.schemas.ai_resume_optimization import (
    ResumeOptimizationResponse,
    ResumeOptimizationListResponse,
    ResumeOptimizationRequest,
    ResumeWorkflowRequest,
    ResumeWorkflowResponse,
    OptimizationMetadata,
)
from app.services.optimization_service import ResumeOptimizationService
from app.services.workflow_service import ResumeWorkflowService
from app.ai.exceptions import AIError

logger = structlog.get_logger()
router = APIRouter()

def map_optimization_to_response(db_opt: AIResumeOptimization) -> ResumeOptimizationResponse:
    """Helper to convert a DB AIResumeOptimization model instance to ResumeOptimizationResponse schema."""
    opt_dict = db_opt.optimization_result
    metadata_dict = db_opt.optimization_metadata or {}
    
    metadata = OptimizationMetadata(
        prompt_version=db_opt.prompt_version,
        model=db_opt.model,
        provider=db_opt.provider,
        created_at=db_opt.created_at,
        latency_ms=metadata_dict.get("latency_ms", 0.0),
        mode=metadata_dict.get("mode", "STANDARD")
    )
    
    return ResumeOptimizationResponse(
        id=db_opt.id,
        user_id=db_opt.user_id,
        resume_id=db_opt.resume_id,
        quality_score=opt_dict.get("quality_score", {}),
        missing_skills=opt_dict.get("missing_skills", []),
        ats_optimization=opt_dict.get("ats_optimization", {}),
        keyword_optimization=opt_dict.get("keyword_optimization", {}),
        achievement_optimization=opt_dict.get("achievement_optimization", []),
        completeness=opt_dict.get("completeness", {}),
        career_readiness=opt_dict.get("career_readiness", {}),
        industry_alignment=opt_dict.get("industry_alignment", []),
        recommendations=opt_dict.get("recommendations", []),
        metadata=metadata,
        created_at=db_opt.created_at,
        updated_at=db_opt.updated_at
    )

@router.post("/resume/optimize", response_model=ResumeOptimizationResponse, status_code=status.HTTP_200_OK)
async def optimize_resume(
    request: ResumeOptimizationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Analyze parsed resume JSON and produce detailed optimization recommendations."""
    service = ResumeOptimizationService(db)
    try:
        db_opt = await service.optimize_resume(
            resume_id=request.resume_id,
            user_id=current_user.id,
            job_description=request.job_description,
            mode=request.mode,
            model_override=request.model_override,
            bypass_cache=request.bypass_cache
        )
        return map_optimization_to_response(db_opt)
    except ValueError as ve:
        logger.warning(
            "resume_optimization_validation_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(ve)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except AIError as ae:
        logger.error(
            "resume_optimization_ai_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(ae)
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Optimization system error: {str(ae)}"
        )
    except Exception as e:
        logger.exception(
            "resume_optimization_internal_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during resume optimization processing."
        )

@router.post("/resume/workflow", response_model=ResumeWorkflowResponse, status_code=status.HTTP_200_OK)
async def run_resume_workflow(
    request: ResumeWorkflowRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute the full sequence pipeline (Parser -> Review -> Rewrite -> Optimize -> Scoring)."""
    service = ResumeWorkflowService(db)
    try:
        workflow_res = await service.execute_workflow(
            resume_id=request.resume_id,
            user_id=current_user.id,
            job_description=request.job_description,
            mode=request.mode,
            model_override=request.model_override,
            bypass_cache=request.bypass_cache
        )
        return workflow_res
    except ValueError as ve:
        logger.warning(
            "resume_workflow_validation_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(ve)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except AIError as ae:
        logger.error(
            "resume_workflow_ai_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(ae)
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Workflow system error: {str(ae)}"
        )
    except Exception as e:
        logger.exception(
            "resume_workflow_internal_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during resume workflow execution."
        )

@router.get("/resume/optimization/{id}", response_model=ResumeOptimizationResponse, status_code=status.HTTP_200_OK)
async def get_resume_optimization(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve specific AI resume optimization details by ID."""
    service = ResumeOptimizationService(db)
    db_opt = await service.get_optimization(optimization_id=id, user_id=current_user.id)
    if not db_opt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Resume Optimization record not found."
        )
    return map_optimization_to_response(db_opt)

@router.get("/resume/optimizations", response_model=ResumeOptimizationListResponse, status_code=status.HTTP_200_OK)
async def get_resume_optimizations(
    resume_id: Optional[uuid.UUID] = Query(None, description="Filter optimizations by resume ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve optimization history for all resumes or filtered by specific resume ID."""
    service = ResumeOptimizationService(db)
    if resume_id:
        db_opts = await service.get_optimizations_for_resume(resume_id=resume_id, user_id=current_user.id)
    else:
        db_opts = db.query(AIResumeOptimization).filter(
            AIResumeOptimization.user_id == current_user.id
        ).order_by(AIResumeOptimization.created_at.desc()).all()
        
    responses = [map_optimization_to_response(opt) for opt in db_opts]
    return ResumeOptimizationListResponse(optimizations=responses, total=len(responses))

@router.delete("/resume/optimization/{id}", status_code=status.HTTP_200_OK)
async def delete_resume_optimization(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an AI resume optimization record by ID."""
    service = ResumeOptimizationService(db)
    success = await service.delete_optimization(optimization_id=id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Resume Optimization record not found or could not be deleted."
        )
    return {"success": True, "message": "Optimization deleted successfully."}
