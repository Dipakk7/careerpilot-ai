import structlog
from typing import Optional

logger = structlog.get_logger()


def log_ai_request(
    provider: str,
    model: str,
    duration_ms: float,
    success: bool,
    error: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
) -> None:
    """Log LLM request metadata and metrics.

    CRITICAL: Never log user prompts, personal information, or resume contents
    to comply with privacy and security requirements.
    """
    log_data = {
        "provider": provider,
        "model": model,
        "duration_ms": round(duration_ms, 2),
        "success": success,
    }

    if error is not None:
        log_data["error"] = error
    if input_tokens is not None:
        log_data["input_tokens"] = input_tokens
    if output_tokens is not None:
        log_data["output_tokens"] = output_tokens

    if success:
        logger.info("llm_request_success", **log_data)
    else:
        logger.error("llm_request_failed", **log_data)
