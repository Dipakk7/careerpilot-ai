from __future__ import annotations
import uuid
from typing import Optional
from sqlalchemy import String, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import SharedBase

class AIResumeRewrite(SharedBase):
    """Database model mapping to the ai_resume_rewrites table."""
    __tablename__ = "ai_resume_rewrites"

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
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_resume_rewrites.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Store the original parsed resume or section JSON
    original_content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Store the rewritten content JSON
    rewritten_content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Rewrite configuration details
    rewrite_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    job_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # LLM execution audit fields
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # SQLAlchemy clashes if we call the column 'metadata' as an attribute.
    # Therefore, we name the attribute 'rewrite_metadata' and map it to database column 'metadata'.
    rewrite_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    resume: Mapped["Resume"] = relationship("Resume")
    parent: Mapped[Optional["AIResumeRewrite"]] = relationship("AIResumeRewrite", remote_side="AIResumeRewrite.id")
