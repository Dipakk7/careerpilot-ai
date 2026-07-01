import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.ai_resume_optimization import AIResumeOptimization

def create_optimization(
    db: Session,
    user_id: uuid.UUID,
    resume_id: uuid.UUID,
    workflow_result: dict | None,
    optimization_result: dict,
    quality_score: dict,
    provider: str,
    model: str,
    prompt_version: str,
    optimization_metadata: dict | None
) -> AIResumeOptimization:
    """Create a new AI resume optimization record."""
    db_opt = AIResumeOptimization(
        user_id=user_id,
        resume_id=resume_id,
        workflow_result=workflow_result,
        optimization_result=optimization_result,
        quality_score=quality_score,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        optimization_metadata=optimization_metadata,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(db_opt)
    db.commit()
    db.refresh(db_opt)
    return db_opt

def get_optimization_by_id(
    db: Session,
    optimization_id: uuid.UUID,
    user_id: uuid.UUID
) -> AIResumeOptimization | None:
    """Retrieve a specific AI resume optimization for a user by its ID."""
    return db.query(AIResumeOptimization).filter(
        AIResumeOptimization.id == optimization_id,
        AIResumeOptimization.user_id == user_id
    ).first()

def get_optimizations_by_resume_id(
    db: Session,
    resume_id: uuid.UUID,
    user_id: uuid.UUID
) -> list[AIResumeOptimization]:
    """Retrieve all AI optimizations for a specific resume, ordered by created_at descending."""
    return db.query(AIResumeOptimization).filter(
        AIResumeOptimization.resume_id == resume_id,
        AIResumeOptimization.user_id == user_id
    ).order_by(desc(AIResumeOptimization.created_at)).all()

def get_user_optimizations(
    db: Session,
    user_id: uuid.UUID
) -> list[AIResumeOptimization]:
    """Retrieve all AI optimizations created by/for a specific user, ordered by created_at descending."""
    return db.query(AIResumeOptimization).filter(
        AIResumeOptimization.user_id == user_id
    ).order_by(desc(AIResumeOptimization.created_at)).all()

def delete_optimization_record(
    db: Session,
    optimization: AIResumeOptimization
) -> bool:
    """Delete an AI optimization record from the database."""
    db.delete(optimization)
    db.commit()
    return True
