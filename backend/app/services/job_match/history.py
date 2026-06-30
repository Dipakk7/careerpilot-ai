from collections import deque
from datetime import datetime, timezone
import uuid
import structlog

logger = structlog.get_logger()

# Bounded list of size 100 (LRU-like FIFO)
_history_cache = deque(maxlen=100)

def add_to_history(
    resume_id: uuid.UUID | str,
    overall_score: int,
    grade: str,
    job_title: str | None,
    company: str | None
) -> None:
    """
    Add a record to the in-memory match history cache.
    """
    record = {
        "resume_id": str(resume_id),
        "timestamp": datetime.now(timezone.utc),
        "overall_score": overall_score,
        "grade": grade,
        "job_title": job_title or "Unknown Title",
        "company": company or "Unknown Company"
    }
    _history_cache.append(record)
    logger.info("job_match_cached", resume_id=str(resume_id), overall_score=overall_score, grade=grade)

def get_recent_matches(resume_id: uuid.UUID | str) -> list[dict]:
    """
    Get recent matches for a specific resume_id, sorted by timestamp descending.
    """
    resume_id_str = str(resume_id)
    matches = [r for r in _history_cache if r["resume_id"] == resume_id_str]
    # Since deque appends to the right, latest items are at the end.
    # Reversing gets the newest first.
    matches.reverse()
    logger.info("job_match_cache_hit", resume_id=resume_id_str, count=len(matches))
    return matches
