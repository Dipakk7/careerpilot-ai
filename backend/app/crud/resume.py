import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.resume import Resume
from app.core.enums import StorageProvider, ResumeStatus

def create_resume(
    db: Session,
    user_id: uuid.UUID,
    original_filename: str,
    stored_filename: str,
    file_path: str,
    file_size: int,
    file_type: str,
    mime_type: str,
    storage_provider: StorageProvider = StorageProvider.LOCAL
) -> Resume:
    """Create a new resume record in the database."""
    db_resume = Resume(
        user_id=user_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_path=file_path,
        storage_provider=storage_provider,
        file_size=file_size,
        file_type=file_type,
        mime_type=mime_type,
        status=ResumeStatus.UPLOADED,
        uploaded_at=datetime.utcnow()
    )
    db.add(db_resume)
    db.commit()
    db.refresh(db_resume)
    return db_resume

def get_resume_by_id(
    db: Session,
    resume_id: uuid.UUID,
    user_id: uuid.UUID
) -> Resume | None:
    """Retrieve a specific resume for a user by id."""
    return db.query(Resume).filter(
        Resume.id == resume_id,
        Resume.user_id == user_id
    ).first()

def get_user_resumes(
    db: Session,
    user_id: uuid.UUID
) -> list[Resume]:
    """Retrieve all resumes uploaded by a specific user, ordered by uploaded_at descending."""
    return db.query(Resume).filter(
        Resume.user_id == user_id
    ).order_by(desc(Resume.uploaded_at)).all()

def delete_resume_record(
    db: Session,
    resume: Resume
) -> bool:
    """Delete a resume record from the database only."""
    db.delete(resume)
    db.commit()
    return True

def update_resume_status(
    db: Session,
    resume: Resume,
    status: ResumeStatus,
    error_message: str | None = None
) -> Resume:
    """Update the processing status of a resume record, with an optional error message."""
    resume.status = status
    if error_message is not None:
        resume.error_message = error_message
    db.commit()
    db.refresh(resume)
    return resume
