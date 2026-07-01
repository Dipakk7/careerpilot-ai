from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from app.core.db import get_db
from datetime import datetime
import structlog

from app.ai.dependencies import get_ai_provider
from app.ai.providers.base import BaseAIProvider

logger = structlog.get_logger()
router = APIRouter()


@router.get("/health", tags=["System"])
async def health_check(
    db: Session = Depends(get_db),
    ai_provider: BaseAIProvider = Depends(get_ai_provider)
):
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("Health check database connection failed", error=str(e))
        db_status = "unhealthy"

    # AI health check
    ai_status = "healthy"
    ai_details = {}
    try:
        ai_details = await ai_provider.health_check()
        if ai_details.get("status") != "healthy":
            ai_status = "unhealthy"
    except Exception as e:
        logger.error("Health check AI provider failed", error=str(e))
        ai_status = "unhealthy"
        ai_details = {"status": "unhealthy", "error": str(e)}

    overall_status = "healthy" if (db_status == "healthy" and ai_status == "healthy") else "unhealthy"

    return {
        "status": overall_status,
        "database": db_status,
        "ai": ai_details,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

