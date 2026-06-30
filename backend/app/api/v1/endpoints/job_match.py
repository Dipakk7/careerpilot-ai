import uuid
import structlog
import time
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.job_match import JobMatchResponse
from app.services import resume_service
from app.services.job_match.parser import parse_job_description
from app.services.job_match import (
    calculate_job_match,
    analyze_resume_gap,
    add_to_history,
    get_recent_matches,
    generate_match_json,
    generate_match_markdown
)


logger = structlog.get_logger()
router = APIRouter()

# In-memory store for the last matched job description text keyed by resume_id
_last_job_descriptions: dict[uuid.UUID, str] = {}


class AnalyzeJobMatchRequest(BaseModel):
    resume_id: uuid.UUID
    job_description: str


@router.post("/analyze", response_model=JobMatchResponse, status_code=status.HTTP_200_OK)
async def analyze_match_json(
    request: AnalyzeJobMatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze a match using a JSON body containing resume_id and job_description text.
    """
    resume_id = request.resume_id
    logger.info("job_match_started", resume_id=str(resume_id))

    # 1. Validate job description is not empty/whitespace
    if not request.job_description or not request.job_description.strip():
        logger.error("job_match_failed", resume_id=str(resume_id), error="Empty job description")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty job description"
        )

    # 2. Load resume and verify ownership
    resume = resume_service.get_resume_by_id(db, resume_id, current_user.id)
    if not resume:
        logger.error("job_match_failed", resume_id=str(resume_id), error="Resume not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    # 3. Ensure parsed_data exists
    if not resume.parsed_data or "data" not in resume.parsed_data:
        logger.error("job_match_failed", resume_id=str(resume_id), error="Resume not parsed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume not parsed"
        )

    try:
        start_total = time.perf_counter()

        # 4. Parse job description
        start_parse = time.perf_counter()
        job_desc = parse_job_description(request.job_description)
        end_parse = time.perf_counter()
        parsing_time = (end_parse - start_parse) * 1000.0
        logger.info("job_description_parsed", resume_id=str(resume_id))

        # 5. Run match engine
        start_match = time.perf_counter()
        match_result = calculate_job_match(resume, job_desc)
        end_match = time.perf_counter()
        matching_time = (end_match - start_match) * 1000.0
        logger.info("job_matching_completed", resume_id=str(resume_id))

        # 6. Run gap analysis
        start_gap = time.perf_counter()
        _ = analyze_resume_gap(resume, job_desc)
        end_gap = time.perf_counter()
        gap_time = (end_gap - start_gap) * 1000.0
        logger.info("gap_analysis_completed", resume_id=str(resume_id))

        end_total = time.perf_counter()
        total_time = (end_total - start_total) * 1000.0

        # Set processing time
        match_result.processing_time_ms = total_time

        # Check performance budget
        if total_time > 500.0:
            logger.warning(
                "performance_warning",
                resume_id=str(resume_id),
                total_time_ms=total_time,
                parsing_time_ms=parsing_time,
                matching_time_ms=matching_time,
                gap_analysis_time_ms=gap_time
            )

        # 7. Cache job description for GET recalculation
        _last_job_descriptions[resume_id] = request.job_description

        # Store in-memory history cache
        add_to_history(
            resume_id=resume_id,
            overall_score=match_result.match_score,
            grade=match_result.grade,
            job_title=job_desc.title,
            company=job_desc.company
        )

        return match_result


    except Exception as e:
        logger.error("job_match_failed", resume_id=str(resume_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job matching analysis failed: {str(e)}"
        )


@router.post("/{resume_id}", response_model=JobMatchResponse, status_code=status.HTTP_200_OK)
async def match_resume_to_job(
    resume_id: uuid.UUID,
    job_description: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Match a resume against a job description uploaded as a .txt file.
    """
    logger.info("job_match_started", resume_id=str(resume_id))

    # 1. Validate file extension and MIME type
    if not job_description.filename:
        logger.error("job_match_failed", resume_id=str(resume_id), error="Empty filename")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty job description"
        )

    filename = job_description.filename.lower()
    if not (filename.endswith(".txt") or job_description.content_type == "text/plain"):
        logger.error("job_match_failed", resume_id=str(resume_id), error="Unsupported file type")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file"
        )

    # 2. Read and validate text content
    try:
        content = await job_description.read()
        text_content = content.decode("utf-8").strip()
    except Exception as e:
        logger.error("job_match_failed", resume_id=str(resume_id), error=f"Decode error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file"
        )

    if not text_content:
        logger.error("job_match_failed", resume_id=str(resume_id), error="Empty job description content")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty job description"
        )

    # 3. Load resume and verify ownership
    resume = resume_service.get_resume_by_id(db, resume_id, current_user.id)
    if not resume:
        logger.error("job_match_failed", resume_id=str(resume_id), error="Resume not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    # 4. Ensure parsed_data exists
    if not resume.parsed_data or "data" not in resume.parsed_data:
        logger.error("job_match_failed", resume_id=str(resume_id), error="Resume not parsed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume not parsed"
        )

    try:
        start_total = time.perf_counter()

        # 5. Parse job description
        start_parse = time.perf_counter()
        job_desc = parse_job_description(text_content)
        end_parse = time.perf_counter()
        parsing_time = (end_parse - start_parse) * 1000.0
        logger.info("job_description_parsed", resume_id=str(resume_id))

        # 6. Run match engine
        start_match = time.perf_counter()
        match_result = calculate_job_match(resume, job_desc)
        end_match = time.perf_counter()
        matching_time = (end_match - start_match) * 1000.0
        logger.info("job_matching_completed", resume_id=str(resume_id))

        # 7. Run gap analysis
        start_gap = time.perf_counter()
        _ = analyze_resume_gap(resume, job_desc)
        end_gap = time.perf_counter()
        gap_time = (end_gap - start_gap) * 1000.0
        logger.info("gap_analysis_completed", resume_id=str(resume_id))

        end_total = time.perf_counter()
        total_time = (end_total - start_total) * 1000.0

        # Set processing time
        match_result.processing_time_ms = total_time

        # Check performance budget
        if total_time > 500.0:
            logger.warning(
                "performance_warning",
                resume_id=str(resume_id),
                total_time_ms=total_time,
                parsing_time_ms=parsing_time,
                matching_time_ms=matching_time,
                gap_analysis_time_ms=gap_time
            )

        # 8. Cache job description for GET recalculation
        _last_job_descriptions[resume_id] = text_content

        # Store in-memory history cache
        add_to_history(
            resume_id=resume_id,
            overall_score=match_result.match_score,
            grade=match_result.grade,
            job_title=job_desc.title,
            company=job_desc.company
        )

        return match_result


    except Exception as e:
        logger.error("job_match_failed", resume_id=str(resume_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job matching failed: {str(e)}"
        )


@router.get("/{resume_id}", response_model=JobMatchResponse, status_code=status.HTTP_200_OK)
async def get_last_match_result(
    resume_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve the last calculated job match result, recalculated live.
    """
    # 1. Load resume and verify ownership
    resume = resume_service.get_resume_by_id(db, resume_id, current_user.id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    # 2. Ensure parsed_data exists
    if not resume.parsed_data or "data" not in resume.parsed_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume not parsed"
        )

    # 3. Retrieve last matched job description text
    job_desc_text = _last_job_descriptions.get(resume_id)
    if not job_desc_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No job match history found for this resume. Please perform a match first."
        )

    logger.info("job_match_started", resume_id=str(resume_id))
    try:
        start_total = time.perf_counter()

        # 4. Parse job description
        start_parse = time.perf_counter()
        job_desc = parse_job_description(job_desc_text)
        end_parse = time.perf_counter()
        parsing_time = (end_parse - start_parse) * 1000.0
        logger.info("job_description_parsed", resume_id=str(resume_id))

        # 5. Run match engine
        start_match = time.perf_counter()
        match_result = calculate_job_match(resume, job_desc)
        end_match = time.perf_counter()
        matching_time = (end_match - start_match) * 1000.0
        logger.info("job_matching_completed", resume_id=str(resume_id))

        # 6. Run gap analysis
        start_gap = time.perf_counter()
        _ = analyze_resume_gap(resume, job_desc)
        end_gap = time.perf_counter()
        gap_time = (end_gap - start_gap) * 1000.0
        logger.info("gap_analysis_completed", resume_id=str(resume_id))

        end_total = time.perf_counter()
        total_time = (end_total - start_total) * 1000.0

        # Set processing time
        match_result.processing_time_ms = total_time

        # Check performance budget
        if total_time > 500.0:
            logger.warning(
                "performance_warning",
                resume_id=str(resume_id),
                total_time_ms=total_time,
                parsing_time_ms=parsing_time,
                matching_time_ms=matching_time,
                gap_analysis_time_ms=gap_time
            )

        return match_result

    except Exception as e:
        logger.error("job_match_failed", resume_id=str(resume_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Live recalculation failed: {str(e)}"
        )


@router.get("/{resume_id}/export/json", status_code=status.HTTP_200_OK)
async def export_match_json(
    resume_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export the job match results as a downloadable JSON file.
    """
    # 1. Load resume and verify ownership
    resume = resume_service.get_resume_by_id(db, resume_id, current_user.id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    # 2. Ensure parsed_data exists
    if not resume.parsed_data or "data" not in resume.parsed_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume not parsed"
        )

    # 3. Retrieve last matched job description text
    job_desc_text = _last_job_descriptions.get(resume_id)
    if not job_desc_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No job match history found for this resume. Please perform a match first."
        )

    try:
        job_desc = parse_job_description(job_desc_text)
        match_result = calculate_job_match(resume, job_desc)
        gap_result = analyze_resume_gap(resume, job_desc)
        
        result = {
            "match": match_result,
            "gap": gap_result
        }
        
        export_content = generate_match_json(result)
        
        logger.info("job_match_exported", resume_id=str(resume_id), format="json")
        
        return Response(
            content=export_content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=job_match_{resume_id}.json"
            }
        )
    except Exception as e:
        logger.error("job_match_export_failed", resume_id=str(resume_id), format="json", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


@router.get("/{resume_id}/export/markdown", status_code=status.HTTP_200_OK)
async def export_match_markdown(
    resume_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export the job match results as a downloadable Markdown file.
    """
    # 1. Load resume and verify ownership
    resume = resume_service.get_resume_by_id(db, resume_id, current_user.id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    # 2. Ensure parsed_data exists
    if not resume.parsed_data or "data" not in resume.parsed_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume not parsed"
        )

    # 3. Retrieve last matched job description text
    job_desc_text = _last_job_descriptions.get(resume_id)
    if not job_desc_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No job match history found for this resume. Please perform a match first."
        )

    try:
        job_desc = parse_job_description(job_desc_text)
        match_result = calculate_job_match(resume, job_desc)
        gap_result = analyze_resume_gap(resume, job_desc)
        
        result = {
            "match": match_result,
            "gap": gap_result
        }
        
        export_content = generate_match_markdown(result)
        
        logger.info("job_match_exported", resume_id=str(resume_id), format="markdown")
        
        return Response(
            content=export_content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=job_match_{resume_id}.md"
            }
        )
    except Exception as e:
        logger.error("job_match_export_failed", resume_id=str(resume_id), format="markdown", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


@router.get("/{resume_id}/history", status_code=status.HTTP_200_OK)
async def get_match_history(
    resume_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve in-memory match history for the specified resume.
    """
    # 1. Load resume and verify ownership
    resume = resume_service.get_resume_by_id(db, resume_id, current_user.id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    # 2. Retrieve history (logs job_match_cache_hit automatically)
    history_records = get_recent_matches(resume_id)
    return history_records

