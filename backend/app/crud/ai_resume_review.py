import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.ai_resume_review import AIResumeReview

def create_review(
    db: Session,
    user_id: uuid.UUID,
    resume_id: uuid.UUID,
    review: dict,
    review_metadata: dict,
    provider: str,
    model: str,
    prompt_version: str
) -> AIResumeReview:
    """Create a new AI resume review record."""
    db_review = AIResumeReview(
        user_id=user_id,
        resume_id=resume_id,
        review=review,
        review_metadata=review_metadata,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review

def get_review_by_id(
    db: Session,
    review_id: uuid.UUID,
    user_id: uuid.UUID
) -> AIResumeReview | None:
    """Retrieve a specific AI resume review for a user by its ID."""
    return db.query(AIResumeReview).filter(
        AIResumeReview.id == review_id,
        AIResumeReview.user_id == user_id
    ).first()

def get_reviews_by_resume_id(
    db: Session,
    resume_id: uuid.UUID,
    user_id: uuid.UUID
) -> list[AIResumeReview]:
    """Retrieve all AI reviews for a specific resume, ordered by created_at descending."""
    return db.query(AIResumeReview).filter(
        AIResumeReview.resume_id == resume_id,
        AIResumeReview.user_id == user_id
    ).order_by(desc(AIResumeReview.created_at)).all()

def get_user_reviews(
    db: Session,
    user_id: uuid.UUID
) -> list[AIResumeReview]:
    """Retrieve all AI reviews created by/for a specific user, ordered by created_at descending."""
    return db.query(AIResumeReview).filter(
        AIResumeReview.user_id == user_id
    ).order_by(desc(AIResumeReview.created_at)).all()

def delete_review_record(
    db: Session,
    review: AIResumeReview
) -> bool:
    """Delete an AI review record from the database."""
    db.delete(review)
    db.commit()
    return True
