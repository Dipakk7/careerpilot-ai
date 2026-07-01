import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, ConfigDict, Field

class ResumeQualityScore(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    ats: int = Field(..., ge=0, le=100)
    technical_skills: int = Field(..., ge=0, le=100)
    experience: int = Field(..., ge=0, le=100)
    projects: int = Field(..., ge=0, le=100)
    grammar: int = Field(..., ge=0, le=100)
    formatting: int = Field(..., ge=0, le=100)
    readability: int = Field(..., ge=0, le=100)
    leadership: int = Field(..., ge=0, le=100)
    professionalism: int = Field(..., ge=0, le=100)
    career_readiness: int = Field(..., ge=0, le=100)
    completeness: int = Field(..., ge=0, le=100)
    consistency: int = Field(..., ge=0, le=100)

    model_config = ConfigDict(from_attributes=True)

class MissingSkillDetail(BaseModel):
    skill: str
    why_it_matters: str
    priority: str  # learning priority (e.g. HIGH, MEDIUM, LOW)
    difficulty: str  # e.g. EASY, MEDIUM, HARD
    estimated_time: str
    resources: List[str]  # recommended resources placeholder

    model_config = ConfigDict(from_attributes=True)

class ATSOptimizationDetail(BaseModel):
    current_score: int = Field(..., ge=0, le=100)
    why_score_is_low: str
    missing_keywords: List[str]
    sections_needing_improvement: List[str]
    expected_improvement: int

    model_config = ConfigDict(from_attributes=True)

class KeywordAnalysis(BaseModel):
    matched_keywords: List[str]
    missing_keywords: List[str]
    recommended_keywords: List[str]
    overused_keywords: List[str]
    weak_keywords: List[str]
    strong_action_verbs: List[str]
    industry_keywords: List[str]

    model_config = ConfigDict(from_attributes=True)

class AchievementOptimizationDetail(BaseModel):
    original_bullet: str
    suggested_bullet: str
    reason: str
    missing_metrics: bool
    missing_impact: bool
    missing_business_value: bool
    estimated_improvement: str

    model_config = ConfigDict(from_attributes=True)

class ResumeCompleteness(BaseModel):
    percentage: int = Field(..., ge=0, le=100)
    missing_sections: List[str]
    evaluated_sections: Dict[str, bool]

    model_config = ConfigDict(from_attributes=True)

class CareerReadinessDetail(BaseModel):
    ready: bool
    reasoning: str

    model_config = ConfigDict(from_attributes=True)

class CareerReadiness(BaseModel):
    internship_ready: CareerReadinessDetail
    entry_level_ready: CareerReadinessDetail
    mid_level_ready: CareerReadinessDetail
    senior_ready: CareerReadinessDetail

    model_config = ConfigDict(from_attributes=True)

class IndustryAlignmentDetail(BaseModel):
    industry: str
    confidence: float = Field(..., ge=0.0, le=1.0)

    model_config = ConfigDict(from_attributes=True)

class OptimizationRecommendation(BaseModel):
    section: str
    type: str
    original_text: Optional[str] = None
    suggested_text: Optional[str] = None
    reason: str
    impact: str
    priority: str
    estimated_improvement: str
    difficulty: str

    model_config = ConfigDict(from_attributes=True)

class OptimizationMetadata(BaseModel):
    prompt_version: str
    model: str
    provider: str
    created_at: datetime
    latency_ms: float
    mode: str

    model_config = ConfigDict(from_attributes=True)

class ResumeOptimizationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    resume_id: uuid.UUID
    quality_score: ResumeQualityScore
    missing_skills: List[MissingSkillDetail]
    ats_optimization: ATSOptimizationDetail
    keyword_optimization: KeywordAnalysis
    achievement_optimization: List[AchievementOptimizationDetail]
    completeness: ResumeCompleteness
    career_readiness: CareerReadiness
    industry_alignment: List[IndustryAlignmentDetail]
    recommendations: List[OptimizationRecommendation]
    metadata: OptimizationMetadata
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ResumeOptimizationListResponse(BaseModel):
    optimizations: List[ResumeOptimizationResponse]
    total: int

    model_config = ConfigDict(from_attributes=True)

class ResumeOptimizationRequest(BaseModel):
    resume_id: uuid.UUID
    job_description: Optional[str] = None
    mode: str = "PROFESSIONAL"
    model_override: Optional[str] = None
    bypass_cache: bool = False

class ResumeWorkflowRequest(BaseModel):
    resume_id: uuid.UUID
    job_description: Optional[str] = None
    mode: str = "PROFESSIONAL"
    model_override: Optional[str] = None
    bypass_cache: bool = False

class ResumeWorkflowResponse(BaseModel):
    resume_id: uuid.UUID
    stages: Dict[str, str]
    quality_score: Optional[int] = None
    optimization_id: Optional[uuid.UUID] = None
    review_id: Optional[uuid.UUID] = None
    rewrite_id: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
