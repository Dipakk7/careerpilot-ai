import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import structlog

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.ai_resume_rewrite import AIResumeRewrite
from app.schemas.ai_resume_rewrite import (
    ResumeRewriteRequest,
    ResumeRewriteSectionRequest,
    ResumeRewriteResponse,
    ResumeRewriteListResponse,
    UndoResponse,
    RewriteMetadata as RewriteMetadataSchema,
)
from app.services.rewrite_service import ResumeRewriteService
from app.ai.exceptions import AIError

logger = structlog.get_logger()
router = APIRouter()

def map_rewrite_to_response(db_rewrite: AIResumeRewrite) -> ResumeRewriteResponse:
    """Helper to convert a DB AIResumeRewrite model instance to ResumeRewriteResponse schema."""
    meta_dict = db_rewrite.rewrite_metadata or {}
    
    metadata = RewriteMetadataSchema(
        prompt_version=db_rewrite.prompt_version,
        model=db_rewrite.model,
        provider=db_rewrite.provider,
        created_at=db_rewrite.created_at,
        latency_ms=meta_dict.get("latency_ms", 0.0),
        mode=db_rewrite.rewrite_mode,
        job_description=db_rewrite.job_description
    )
    
    return ResumeRewriteResponse(
        id=db_rewrite.id,
        user_id=db_rewrite.user_id,
        resume_id=db_rewrite.resume_id,
        parent_id=db_rewrite.parent_id,
        original_content=db_rewrite.original_content,
        rewritten_content=db_rewrite.rewritten_content,
        rewrite_mode=db_rewrite.rewrite_mode,
        job_description=db_rewrite.job_description,
        change_tracking=meta_dict.get("change_tracking", {}),
        quality_scores=meta_dict.get("quality_scores", {
            "readability_improvement": 0,
            "grammar_improvement": 0,
            "professional_tone": 0,
            "ats_optimization": 0,
            "action_verb_score": 0
        }),
        keyword_optimization=meta_dict.get("keyword_optimization"),
        metadata=metadata,
        created_at=db_rewrite.created_at,
        updated_at=db_rewrite.updated_at
    )

@router.post("/resume/rewrite", response_model=ResumeRewriteResponse, status_code=status.HTTP_200_OK)
async def rewrite_resume(
    request: ResumeRewriteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Rewrite entire resume according to target mode and job description."""
    service = ResumeRewriteService(db)
    
    try:
        db_rewrite = await service.rewrite_resume(
            resume_id=request.resume_id,
            user_id=current_user.id,
            mode=request.mode,
            job_description=request.job_description,
            model_override=request.model_override,
            bypass_cache=request.bypass_cache
        )
        return map_rewrite_to_response(db_rewrite)
        
    except ValueError as ve:
        logger.warning(
            "resume_rewrite_validation_failed",
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
            "resume_rewrite_ai_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(ae)
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Rewrite system error: {str(ae)}"
        )
        
    except Exception as e:
        logger.exception(
            "resume_rewrite_internal_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during resume rewrite processing."
        )

@router.post("/resume/rewrite/section", response_model=ResumeRewriteResponse, status_code=status.HTTP_200_OK)
async def rewrite_resume_section(
    request: ResumeRewriteSectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Rewrite a specific section of a resume."""
    service = ResumeRewriteService(db)
    
    try:
        db_rewrite = await service.rewrite_resume(
            resume_id=request.resume_id,
            user_id=current_user.id,
            mode=request.mode,
            section_name=request.section_name,
            job_description=request.job_description,
            model_override=request.model_override,
            bypass_cache=request.bypass_cache
        )
        return map_rewrite_to_response(db_rewrite)
        
    except ValueError as ve:
        logger.warning(
            "resume_rewrite_section_validation_failed",
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
            "resume_rewrite_section_ai_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(ae)
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Rewrite system error: {str(ae)}"
        )
        
    except Exception as e:
        logger.exception(
            "resume_rewrite_section_internal_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during resume section rewrite processing."
        )

@router.get("/resume/rewrite/{id}", response_model=ResumeRewriteResponse, status_code=status.HTTP_200_OK)
async def get_resume_rewrite(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve a specific AI resume rewrite details by ID."""
    service = ResumeRewriteService(db)
    db_rewrite = await service.get_rewrite(rewrite_id=id, user_id=current_user.id)
    
    if not db_rewrite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Resume Rewrite not found."
        )
        
    return map_rewrite_to_response(db_rewrite)

@router.get("/resume/rewrites", response_model=ResumeRewriteListResponse, status_code=status.HTTP_200_OK)
async def get_resume_rewrites(
    resume_id: Optional[uuid.UUID] = Query(None, description="Filter rewrites by resume ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve rewrite history for all resumes or filtered by a specific resume."""
    service = ResumeRewriteService(db)
    
    if resume_id:
        db_rewrites = await service.get_rewrites_for_resume(resume_id=resume_id, user_id=current_user.id)
    else:
        db_rewrites = service.db.query(AIResumeRewrite).filter(
            AIResumeRewrite.user_id == current_user.id
        ).order_by(AIResumeRewrite.created_at.desc()).all()
        
    responses = [map_rewrite_to_response(rew) for rew in db_rewrites]
    return ResumeRewriteListResponse(rewrites=responses, total=len(responses))

@router.delete("/resume/rewrite/{id}", status_code=status.HTTP_200_OK)
async def delete_resume_rewrite(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an AI resume rewrite record by ID."""
    service = ResumeRewriteService(db)
    success = await service.delete_rewrite(rewrite_id=id, user_id=current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Resume Rewrite not found or could not be deleted."
        )
        
    return {"success": True, "message": "Rewrite deleted successfully."}

@router.post("/resume/rewrite/{id}/undo", response_model=UndoResponse, status_code=status.HTTP_200_OK)
async def undo_resume_rewrite(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Rollback the active resume content to the state before this rewrite was applied."""
    service = ResumeRewriteService(db)
    try:
        res = await service.rollback_rewrite(rewrite_id=id, user_id=current_user.id)
        return UndoResponse(
            success=res["success"],
            message=res["message"],
            rolled_back_to_id=res["rolled_back_to_id"],
            resume_id=res["resume_id"]
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback rewrite: {str(e)}"
        )
