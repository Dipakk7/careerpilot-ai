from datetime import datetime
from typing import List
from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import SharedBase

class User(SharedBase):
    """User database model mapping to the users table."""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    auth_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'LOCAL'")
    )
    provider_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    profile_picture: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True
    )
    is_verified: Mapped[bool] = mapped_column(
        nullable=False,
        default=False
    )
    last_login: Mapped[datetime | None] = mapped_column(
        nullable=True
    )

    resumes: Mapped[List["Resume"]] = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
