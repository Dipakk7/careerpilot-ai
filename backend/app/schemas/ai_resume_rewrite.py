from datetime import datetime
from uuid import UUID
from enum import Enum
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, ConfigDict, Field

class ImprovementCategory(str, Enum):
    GRAMMAR = "Grammar"
    PROFESSIONAL_TONE = "Professional Tone"
    ATS = "ATS"
    TECHNICAL = "Technical"
    LEADERSHIP = "Leadership"
    COMMUNICATION = "Communication"
    IMPACT = "Impact"

class SectionDiff(BaseModel):
    added: List[str]
    removed: List[str]
    modified: List[Dict[str, str]]

    model_config = ConfigDict(from_attributes=True)

class ChangeTracking(BaseModel):
    original: str
    rewritten: str
    reason: str
    improvement_category: ImprovementCategory
    confidence: float = Field(..., ge=0.0, le=1.0)
    estimated_ats_improvement: float
    diff: Optional[SectionDiff] = None

    model_config = ConfigDict(from_attributes=True)

class RewriteQualityScore(BaseModel):
    readability_improvement: int = Field(..., ge=-100, le=100)
    grammar_improvement: int = Field(..., ge=-100, le=100)
    professional_tone: int = Field(..., ge=-100, le=100)
    ats_optimization: int = Field(..., ge=-100, le=100)
    action_verb_score: int = Field(..., ge=-100, le=100)

    model_config = ConfigDict(from_attributes=True)

class KeywordOptimization(BaseModel):
    matched_keywords: List[str]
    added_keywords: List[str]
    missing_keywords: List[str]

    model_config = ConfigDict(from_attributes=True)

class RewriteMetadata(BaseModel):
    prompt_version: str
    model: str
    provider: str
    created_at: datetime
    latency_ms: float
    mode: str
    job_description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class RewriteSection(BaseModel):
    section_name: str
    original: str
    rewritten: str
    change_tracking: ChangeTracking

    model_config = ConfigDict(from_attributes=True)

class ResumeRewriteRequest(BaseModel):
    resume_id: UUID
    mode: str = "STANDARD"
    job_description: Optional[str] = None
    model_override: Optional[str] = None
    bypass_cache: bool = False

class ResumeRewriteSectionRequest(BaseModel):
    resume_id: UUID
    section_name: str
    mode: str = "STANDARD"
    job_description: Optional[str] = None
    model_override: Optional[str] = None
    bypass_cache: bool = False

class ResumeRewriteResponse(BaseModel):
    id: UUID
    user_id: UUID
    resume_id: UUID
    parent_id: Optional[UUID] = None
    original_content: Dict[str, Any]
    rewritten_content: Dict[str, Any]
    rewrite_mode: str
    job_description: Optional[str] = None
    change_tracking: Dict[str, ChangeTracking]
    quality_scores: RewriteQualityScore
    keyword_optimization: Optional[KeywordOptimization] = None
    metadata: RewriteMetadata
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class RewriteHistory(BaseModel):
    id: UUID
    resume_id: UUID
    rewrite_mode: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ResumeRewriteListResponse(BaseModel):
    rewrites: List[ResumeRewriteResponse]
    total: int

    model_config = ConfigDict(from_attributes=True)

class UndoResponse(BaseModel):
    success: bool
    message: str
    rolled_back_to_id: Optional[UUID] = None
    resume_id: UUID

    model_config = ConfigDict(from_attributes=True)
