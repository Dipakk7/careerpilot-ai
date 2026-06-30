from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.resume import router as resume_router
from app.api.v1.endpoints.ats import router as ats_router
from app.api.v1.endpoints.job_match import router as job_match_router

api_router = APIRouter()

api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"]
)

api_router.include_router(
    resume_router,
    prefix="/resumes",
    tags=["Resume"]
)

api_router.include_router(
    ats_router,
    prefix="/resumes",
    tags=["ATS"]
)

api_router.include_router(
    job_match_router,
    prefix="/job-match",
    tags=["Job Matching"]
)



@api_router.get("", tags=["System"])
async def get_v1_index():
    return {
        "version": "1.0",
        "modules": {
            "auth": "placeholder",
            "resumes": "placeholder",
            "jobs": "placeholder",
            "interviews": "placeholder",
            "chats": "placeholder"
        }
    }
