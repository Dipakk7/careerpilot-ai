from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.resume import router as resume_router
from app.api.v1.endpoints.ats import router as ats_router
from app.api.v1.endpoints.job_match import router as job_match_router
from app.analytics.router import router as analytics_router
from app.api.v1.endpoints.ai_resume_review import router as ai_review_router
from app.api.v1.endpoints.ai_resume_rewrite import router as ai_rewrite_router
from app.api.v1.endpoints.ai_resume_optimization import router as ai_optimization_router

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
    ai_review_router,
    prefix="/ai",
    tags=["AI Resume Review"]
)

api_router.include_router(
    ai_rewrite_router,
    prefix="/ai",
    tags=["AI Resume Rewrite"]
)

api_router.include_router(
    ai_optimization_router,
    prefix="/ai",
    tags=["AI Resume Optimization"]
)

api_router.include_router(
    job_match_router,
    prefix="/job-match",
    tags=["Job Matching"]
)

api_router.include_router(
    analytics_router,
    prefix="/analytics",
    tags=["Analytics"]
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
