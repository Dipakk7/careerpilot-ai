import uuid
from sqlalchemy import String, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import SharedBase

class AIResumeReview(SharedBase):
    """Database model mapping to the ai_resume_reviews table."""
    __tablename__ = "ai_resume_reviews"

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
    
    # Store the parsed resume review JSON
    review: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # SQLAlchemy clashes if we call the column 'metadata' as an attribute.
    # Therefore, we name the attribute 'review_metadata' and map it to database column 'metadata'.
    review_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User")
    resume: Mapped["Resume"] = relationship("Resume")
