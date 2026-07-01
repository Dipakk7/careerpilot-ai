from datetime import datetime
from uuid import UUID
from enum import Enum
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, ConfigDict, Field

class PriorityLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class Recommendation(BaseModel):
    priority: PriorityLevel
    reason: str
    impact: str
    suggested_fix: str
    estimated_benefit: str

    model_config = ConfigDict(from_attributes=True)

class ResumeSectionReview(BaseModel):
    score: int = Field(..., ge=0, le=100)
    feedback: str
    recommendations: List[Recommendation]

    model_config = ConfigDict(from_attributes=True)

class ReviewMetadata(BaseModel):
    prompt_version: str
    model: str
    provider: str
    created_at: datetime
    latency_ms: float
    review_version: str
    mode: str
    language: str

    model_config = ConfigDict(from_attributes=True)

class ResumeReviewResponse(BaseModel):
    id: UUID
    user_id: UUID
    resume_id: UUID
    overall_score: int = Field(..., ge=0, le=100)
    overall_summary: str
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[Recommendation]
    missing_sections: List[str]
    grammar_feedback: str
    ats_feedback: str
    technical_feedback: str
    career_feedback: str
    priority_improvements: List[Recommendation]
    confidence: float = Field(..., ge=0.0, le=1.0)
    sections: Dict[str, ResumeSectionReview]
    metadata: ReviewMetadata
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ResumeReviewListResponse(BaseModel):
    reviews: List[ResumeReviewResponse]
    total: int

    model_config = ConfigDict(from_attributes=True)
