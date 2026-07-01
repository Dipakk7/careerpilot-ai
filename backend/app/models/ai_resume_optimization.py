import uuid
from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import SharedBase

class AIResumeOptimization(SharedBase):
    """Database model mapping to the ai_resume_optimizations table."""
    __tablename__ = "ai_resume_optimizations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Store the results of workflow pipeline execution
    workflow_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Store the parsed resume optimization recommendations JSON
    optimization_result: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Store the quality score details JSON (overall and category scores)
    quality_score: Mapped[dict] = mapped_column(JSONB, nullable=False)

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # Database column is 'metadata'. We name the attribute 'optimization_metadata' to avoid SQLAlchemy conflicts.
    optimization_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    resume: Mapped["Resume"] = relationship("Resume")
