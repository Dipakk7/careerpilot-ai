import uuid
import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import structlog

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.ats import ATSScoreResponse
from app.services import resume_service
from app.services.ats.ats_service import calculate_ats_score

logger = structlog.get_logger()
router = APIRouter()


@router.post("/{resume_id}/score", response_model=ATSScoreResponse, status_code=status.HTTP_200_OK)
async def score_resume(
    resume_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate and save the ATS score for a specific resume owned by the current user.
    
    The resume must be parsed before scoring.
    """
    resume = resume_service.get_resume_by_id(
        db=db,
        resume_id=resume_id,
        user_id=current_user.id
    )
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    if resume.parsed_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume must be parsed before ATS scoring."
        )

    start_time = time.time()
    logger.info(
        "ats_score_started",
        resume_id=str(resume_id),
        user_id=str(current_user.id)
    )

    try:
        score_response = calculate_ats_score(resume)
        db.commit()
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "ats_score_completed",
            resume_id=str(resume_id),
            user_id=str(current_user.id),
            overall_score=score_response.overall_score,
            grade=score_response.grade,
            processing_time_ms=processing_time_ms
        )
        return score_response
    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "ats_score_failed",
            resume_id=str(resume_id),
            user_id=str(current_user.id),
            processing_time_ms=processing_time_ms,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ATS scoring failed: {str(e)}"
        )


@router.get("/{resume_id}/score", response_model=ATSScoreResponse, status_code=status.HTTP_200_OK)
async def get_resume_score(
    resume_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve the ATS score details for a specific resume, recalculated live."""
    resume = resume_service.get_resume_by_id(
        db=db,
        resume_id=resume_id,
        user_id=current_user.id
    )
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    if resume.parsed_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume must be parsed before ATS scoring."
        )

    start_time = time.time()
    logger.info(
        "ats_score_started",
        resume_id=str(resume_id),
        user_id=str(current_user.id)
    )

    try:
        # We always recalculate live to ensure recommendations remain current
        score_response = calculate_ats_score(resume)
        db.commit()
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "ats_score_completed",
            resume_id=str(resume_id),
            user_id=str(current_user.id),
            overall_score=score_response.overall_score,
            grade=score_response.grade,
            processing_time_ms=processing_time_ms
        )
        return score_response
    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "ats_score_failed",
            resume_id=str(resume_id),
            user_id=str(current_user.id),
            processing_time_ms=processing_time_ms,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ATS scoring failed: {str(e)}"
        )
