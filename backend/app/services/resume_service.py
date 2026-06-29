import os
import uuid
import magic
import structlog
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException

from app.core.config import settings
from app.core.enums import StorageProvider, ResumeStatus
from app.models.resume import Resume
from app.models.user import User
from app.crud import resume as crud
from app.services import storage_service

# Magic bytes signature mapping
MAGIC_BYTES = {
    "pdf": b"%PDF-",
    "docx": b"PK\x03\x04"
}

logger = structlog.get_logger()

def validate_file_extension(
    filename: str
) -> tuple[bool, str]:
    """Validate that the file extension is allowed and return the normalized extension."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower().strip(".")
    if ext in settings.ALLOWED_EXTENSIONS:
        return True, ext
    allowed_list = ", ".join(settings.ALLOWED_EXTENSIONS)
    return False, f"Extension '.{ext}' is not allowed. Allowed: {allowed_list}"

def validate_mime_type(
    file_content: bytes,
    expected_extension: str
) -> tuple[bool, str]:
    """Validate that the file's MIME type matches the expected extension using magic and signature fallbacks."""
    expected_mime = settings.ALLOWED_MIME_TYPES.get(expected_extension)
    if not expected_mime:
        return False, f"Unsupported extension: {expected_extension}"
        
    detected_mime = None
    try:
        # Primary check using python-magic
        detected_mime = magic.from_buffer(file_content, mime=True)
        if detected_mime == expected_mime:
            return True, detected_mime
    except Exception as e:
        logger.warning(f"python-magic failed to detect MIME type: {str(e)}")
        
    # Fallback check using magic bytes signature
    magic_signature = MAGIC_BYTES.get(expected_extension)
    if magic_signature and file_content.startswith(magic_signature):
        return True, expected_mime
        
    actual_mime_desc = detected_mime if detected_mime else "unknown"
    return False, f"MIME type validation failed. Expected: '{expected_mime}', got: '{actual_mime_desc}'"

async def process_upload(
    db: Session,
    file: UploadFile,
    current_user: User
) -> Resume:
    """Orchestrates validation, filesystem saving, and database creation with automatic cleanup on failure."""
    saved_file_path = None
    db_record_created = False
    
    logger.info(
        "resume_upload_started",
        user_id=str(current_user.id),
        filename=file.filename
    )
    
    try:
        # Step 1: Validate extension
        ok, ext = validate_file_extension(file.filename)
        if not ok:
            raise HTTPException(status_code=400, detail=ext)
            
        # Step 2: Read file content into memory
        file_content = await file.read()
        
        # Step 3: Validate file size (MAX_FILE_SIZE_MB)
        file_size = len(file_content)
        file_size_mb = file_size / (1024 * 1024)
        if file_size_mb > settings.MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed limit of {settings.MAX_FILE_SIZE_MB}MB"
            )
            
        # Step 4: Validate MIME type
        ok, detected_mime = validate_mime_type(file_content, ext)
        if not ok:
            raise HTTPException(status_code=400, detail=detected_mime)
            
        logger.info(
            "resume_file_validated",
            user_id=str(current_user.id),
            file_type=ext,
            mime_type=detected_mime,
            file_size=file_size
        )
        
        # Step 5: Generate stored filename
        stored_filename = storage_service.generate_filename(current_user.id, file.filename)
        
        # Step 6: Save file to storage
        saved_file_path, file_size = await storage_service.save_file(
            file_content=file_content,
            stored_filename=stored_filename,
            provider=StorageProvider.LOCAL
        )
        
        # Step 7: Create database record
        db_resume = crud.create_resume(
            db=db,
            user_id=current_user.id,
            original_filename=file.filename,
            stored_filename=stored_filename,
            file_path=saved_file_path,
            file_size=file_size,
            file_type=ext,
            mime_type=detected_mime,
            storage_provider=StorageProvider.LOCAL
        )
        db_record_created = True
        
        logger.info(
            "resume_upload_completed",
            resume_id=str(db_resume.id),
            user_id=str(current_user.id),
            file_type=ext,
            file_size=file_size
        )
        
        # Step 8: Return Resume
        return db_resume
        
    except HTTPException as he:
        logger.error(
            "resume_upload_failed",
            reason=he.detail,
            user_id=str(current_user.id)
        )
        # Re-raise standard HTTPExceptions (like validation errors or 413)
        raise
    except Exception as e:
        logger.error(
            "resume_upload_failed",
            reason=str(e),
            user_id=str(current_user.id)
        )
        logger.exception(f"Unexpected error while processing resume upload: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing the upload"
        )
    finally:
        # Step 9: Safe cleanup if database record creation failed
        if saved_file_path and not db_record_created:
            storage_service.delete_file(saved_file_path, StorageProvider.LOCAL)
            logger.info(f"Cleaned up saved file '{saved_file_path}' because database transaction failed.")

def delete_resume(
    db: Session,
    resume: Resume
) -> bool:
    """Orchestrates file deletion first, followed by database record deletion to avoid orphans."""
    # Step 1: Delete file from storage
    storage_service.delete_file(resume.file_path, resume.storage_provider)
    
    # Step 2: Delete database record
    crud.delete_resume_record(db, resume)
    
    logger.info(
        "resume_deleted",
        resume_id=str(resume.id),
        user_id=str(resume.user_id)
    )
    
    # Step 3: Return True
    return True

def get_user_resumes(
    db: Session,
    user_id: uuid.UUID
) -> list[Resume]:
    """Retrieve all resumes uploaded by a specific user."""
    return crud.get_user_resumes(db, user_id)

def get_resume_by_id(
    db: Session,
    resume_id: uuid.UUID,
    user_id: uuid.UUID
) -> Resume | None:
    """Retrieve a specific resume for a user by id."""
    return crud.get_resume_by_id(db, resume_id, user_id)

