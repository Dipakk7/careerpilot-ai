import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.ai_resume_rewrite import AIResumeRewrite

def create_rewrite(
    db: Session,
    user_id: uuid.UUID,
    resume_id: uuid.UUID,
    original_content: dict,
    rewritten_content: dict,
    rewrite_mode: str,
    job_description: str | None,
    provider: str,
    model: str,
    prompt_version: str,
    rewrite_metadata: dict,
    parent_id: uuid.UUID | None = None
) -> AIResumeRewrite:
    """Create a new AI resume rewrite record."""
    db_rewrite = AIResumeRewrite(
        user_id=user_id,
        resume_id=resume_id,
        parent_id=parent_id,
        original_content=original_content,
        rewritten_content=rewritten_content,
        rewrite_mode=rewrite_mode,
        job_description=job_description,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        rewrite_metadata=rewrite_metadata,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(db_rewrite)
    db.commit()
    db.refresh(db_rewrite)
    return db_rewrite

def get_rewrite_by_id(
    db: Session,
    rewrite_id: uuid.UUID,
    user_id: uuid.UUID
) -> AIResumeRewrite | None:
    """Retrieve a specific AI resume rewrite for a user by its ID."""
    return db.query(AIResumeRewrite).filter(
        AIResumeRewrite.id == rewrite_id,
        AIResumeRewrite.user_id == user_id
    ).first()

def get_rewrites_by_resume_id(
    db: Session,
    resume_id: uuid.UUID,
    user_id: uuid.UUID
) -> list[AIResumeRewrite]:
    """Retrieve all AI rewrites for a specific resume, ordered by created_at descending."""
    return db.query(AIResumeRewrite).filter(
        AIResumeRewrite.resume_id == resume_id,
        AIResumeRewrite.user_id == user_id
    ).order_by(desc(AIResumeRewrite.created_at)).all()

def get_user_rewrites(
    db: Session,
    user_id: uuid.UUID
) -> list[AIResumeRewrite]:
    """Retrieve all AI rewrites created by/for a specific user, ordered by created_at descending."""
    return db.query(AIResumeRewrite).filter(
        AIResumeRewrite.user_id == user_id
    ).order_by(desc(AIResumeRewrite.created_at)).all()

def delete_rewrite_record(
    db: Session,
    rewrite: AIResumeRewrite
) -> bool:
    """Delete an AI rewrite record from the database."""
    db.delete(rewrite)
    db.commit()
    return True
