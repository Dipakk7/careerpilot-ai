from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class SkillGap(BaseModel):
    matched: list[str]
    missing_required: list[str]
    missing_preferred: list[str]
    extra_resume_skills: list[str]

    model_config = ConfigDict(from_attributes=True)

class ExperienceGap(BaseModel):
    matched: bool
    required: str
    resume: str
    gap: str

    model_config = ConfigDict(from_attributes=True)

class EducationGap(BaseModel):
    matched: bool
    required: str
    resume: str
    gap: str

    model_config = ConfigDict(from_attributes=True)

class CertificationGap(BaseModel):
    matched: list[str]
    missing: list[str]

    model_config = ConfigDict(from_attributes=True)

class KeywordGap(BaseModel):
    matched: list[str]
    missing: list[str]

    model_config = ConfigDict(from_attributes=True)

class GapAnalysisResponse(BaseModel):
    resume_id: UUID
    overall_match: bool
    skill_gap: SkillGap
    experience_gap: ExperienceGap
    education_gap: EducationGap
    certification_gap: CertificationGap
    keyword_gap: KeywordGap
    priority_improvements: list[dict]
    analysis_version: str
    analyzed_at: datetime

    model_config = ConfigDict(from_attributes=True)
