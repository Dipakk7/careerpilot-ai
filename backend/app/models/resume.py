import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Text, text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import SharedBase
from app.core.enums import StorageProvider, ResumeStatus

class Resume(SharedBase):
    """Resume database model mapping to the resumes table."""
    __tablename__ = "resumes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    stored_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    storage_provider: Mapped[StorageProvider] = mapped_column(
        SQLEnum(StorageProvider, native_enum=False, length=20),
        nullable=False,
        server_default=text(f"'{StorageProvider.LOCAL.value}'")
    )
    file_size: Mapped[int] = mapped_column(
        nullable=False
    )
    file_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    status: Mapped[ResumeStatus] = mapped_column(
        SQLEnum(ResumeStatus, native_enum=False, length=20),
        nullable=False,
        server_default=text(f"'{ResumeStatus.UPLOADED.value}'")
    )
    raw_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    parsed_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True
    )
    ats_score: Mapped[int | None] = mapped_column(
        nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now()
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="resumes")
