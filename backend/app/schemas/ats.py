from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator
from app.core.ats_constants import RECOMMENDATION_CATEGORIES, RECOMMENDATION_PRIORITIES

class ATSBreakdown(BaseModel):
    contact: int
    skills: int
    education: int
    experience: int
    projects: int
    certifications: int

    model_config = ConfigDict(from_attributes=True)

class ATSRecommendation(BaseModel):
    category: str
    priority: str
    message: str

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in RECOMMENDATION_CATEGORIES:
            raise ValueError(f"category must be one of {RECOMMENDATION_CATEGORIES}")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in RECOMMENDATION_PRIORITIES:
            raise ValueError(f"priority must be one of {RECOMMENDATION_PRIORITIES}")
        return v

    model_config = ConfigDict(from_attributes=True)

class ATSScoreResponse(BaseModel):
    resume_id: UUID
    overall_score: int
    grade: str
    grade_summary: str
    breakdown: ATSBreakdown
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[ATSRecommendation]
    parser_version: str
    ats_version: str
    scored_at: datetime

    model_config = ConfigDict(from_attributes=True)
