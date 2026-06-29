from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class ResumeResponse(BaseModel):
    id: UUID
    user_id: UUID
    original_filename: str
    file_size: int
    file_type: str
    storage_provider: str
    status: str
    ats_score: int | None
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ResumeListResponse(BaseModel):
    resumes: list[ResumeResponse]
    total: int

class ResumeUploadResponse(BaseModel):
    message: str
    resume: ResumeResponse
    next_step: str = "Ready for parsing"
