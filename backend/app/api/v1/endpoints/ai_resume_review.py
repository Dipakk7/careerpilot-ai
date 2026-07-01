import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import structlog
from pydantic import BaseModel

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.ai_resume_review import AIResumeReview
from app.schemas.ai_resume_review import (
    ResumeReviewResponse,
    ResumeReviewListResponse,
    ReviewMetadata,
)
from app.services.review_service import ResumeReviewService
from app.ai.exceptions import AIError

logger = structlog.get_logger()
router = APIRouter()

class ResumeReviewRequest(BaseModel):
    resume_id: uuid.UUID
    mode: str = "STANDARD"
    language: str = "en"
    model_override: Optional[str] = None
    bypass_cache: bool = False


def map_review_to_response(db_review: AIResumeReview) -> ResumeReviewResponse:
    """Helper to convert a DB AIResumeReview model instance to ResumeReviewResponse schema."""
    review_dict = db_review.review
    metadata_dict = db_review.review_metadata or {}
    
    metadata = ReviewMetadata(
        prompt_version=db_review.prompt_version,
        model=db_review.model,
        provider=db_review.provider,
        created_at=db_review.created_at,
        latency_ms=metadata_dict.get("latency_ms", 0.0),
        review_version=metadata_dict.get("review_version", "1.0.0"),
        mode=metadata_dict.get("mode", "STANDARD"),
        language=metadata_dict.get("language", "en")
    )
    
    return ResumeReviewResponse(
        id=db_review.id,
        user_id=db_review.user_id,
        resume_id=db_review.resume_id,
        overall_score=review_dict.get("overall_score", 0),
        overall_summary=review_dict.get("overall_summary", ""),
        strengths=review_dict.get("strengths", []),
        weaknesses=review_dict.get("weaknesses", []),
        recommendations=review_dict.get("recommendations", []),
        missing_sections=review_dict.get("missing_sections", []),
        grammar_feedback=review_dict.get("grammar_feedback", ""),
        ats_feedback=review_dict.get("ats_feedback", ""),
        technical_feedback=review_dict.get("technical_feedback", ""),
        career_feedback=review_dict.get("career_feedback", ""),
        priority_improvements=review_dict.get("priority_improvements", []),
        confidence=review_dict.get("confidence", 0.0),
        sections=review_dict.get("sections", {}),
        metadata=metadata,
        created_at=db_review.created_at,
        updated_at=db_review.updated_at
    )


@router.post("/resume/review", response_model=ResumeReviewResponse, status_code=status.HTTP_200_OK)
async def review_resume(
    request: ResumeReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Analyze parsed resume JSON and produce detailed, structured review feedback."""
    service = ResumeReviewService(db)
    
    try:
        db_review = await service.review_resume(
            resume_id=request.resume_id,
            user_id=current_user.id,
            mode=request.mode,
            language=request.language,
            model_override=request.model_override,
            bypass_cache=request.bypass_cache
        )
        return map_review_to_response(db_review)
        
    except ValueError as ve:
        # Client validation/formatting errors
        logger.warning(
            "resume_review_validation_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(ve)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
        
    except AIError as ae:
        # Standardized AI request failure
        logger.error(
            "resume_review_ai_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(ae)
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Review system error: {str(ae)}"
        )
        
    except Exception as e:
        # General unhandled exceptions
        logger.exception(
            "resume_review_internal_failed",
            resume_id=str(request.resume_id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during resume review processing."
        )


@router.get("/resume/review/{id}", response_model=ResumeReviewResponse, status_code=status.HTTP_200_OK)
async def get_resume_review(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve a specific AI resume review details by ID."""
    service = ResumeReviewService(db)
    db_review = await service.get_review(review_id=id, user_id=current_user.id)
    
    if not db_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Resume Review not found."
        )
        
    return map_review_to_response(db_review)


@router.get("/resume/reviews", response_model=ResumeReviewListResponse, status_code=status.HTTP_200_OK)
async def get_resume_reviews(
    resume_id: Optional[uuid.UUID] = Query(None, description="Filter reviews by resume ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve review history for all resumes or filtered by a specific resume."""
    service = ResumeReviewService(db)
    
    if resume_id:
        db_reviews = await service.get_reviews_for_resume(resume_id=resume_id, user_id=current_user.id)
    else:
        db_reviews = service.db.query(AIResumeReview).filter(
            AIResumeReview.user_id == current_user.id
        ).order_by(AIResumeReview.created_at.desc()).all()
        
    responses = [map_review_to_response(rev) for rev in db_reviews]
    return ResumeReviewListResponse(reviews=responses, total=len(responses))


@router.delete("/resume/review/{id}", status_code=status.HTTP_200_OK)
async def delete_resume_review(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an AI resume review record by ID."""
    service = ResumeReviewService(db)
    success = await service.delete_review(review_id=id, user_id=current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Resume Review not found or could not be deleted."
        )
        
    return {"success": True, "message": "Review deleted successfully."}
