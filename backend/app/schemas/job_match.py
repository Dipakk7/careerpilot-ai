from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator
from app.core.job_match_constants import RECOMMENDATION_PRIORITY

class JobDescription(BaseModel):
    title: str | None = None
    company: str | None = None
    required_skills: list[str]
    preferred_skills: list[str]
    education: list[str]
    experience: list[str]
    certifications: list[str]
    responsibilities: list[str]
    keywords: list[str]
    raw_text: str

    model_config = ConfigDict(from_attributes=True)

class MatchBreakdown(BaseModel):
    skills: int
    experience: int
    education: int
    certifications: int
    keywords: int

    model_config = ConfigDict(from_attributes=True)

class MatchRecommendation(BaseModel):
    category: str
    priority: str
    message: str

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in RECOMMENDATION_PRIORITY:
            raise ValueError(f"priority must be one of {RECOMMENDATION_PRIORITY}")
        return v

    model_config = ConfigDict(from_attributes=True)

class JobMatchResponse(BaseModel):
    resume_id: UUID
    match_score: int
    grade: str
    breakdown: MatchBreakdown
    matched_skills: list[str]
    missing_skills: list[str]
    extra_skills: list[str]
    recommendations: list[MatchRecommendation]
    parser_version: str
    ats_version: str
    job_match_version: str
    generated_at: datetime
    processing_time_ms: float | None = None

    model_config = ConfigDict(from_attributes=True)

