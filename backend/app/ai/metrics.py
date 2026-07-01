import threading
import structlog
from typing import Dict, Any, List

logger = structlog.get_logger()

class AIMetricsCollector:
    """Thread-safe collector for AI service metrics."""

    def __init__(self):
        self._lock = threading.Lock()
        self.cache_hits = 0
        self.cache_misses = 0
        self.retries = 0
        self.failures = 0
        self.successes = 0
        self.request_durations: List[float] = []

    def record_cache_hit(self, provider: str, model: str, prompt_version: str) -> None:
        with self._lock:
            self.cache_hits += 1
        logger.info(
            "ai_cache_hit",
            provider=provider,
            model=model,
            prompt_version=prompt_version
        )

    def record_cache_miss(self, provider: str, model: str, prompt_version: str) -> None:
        with self._lock:
            self.cache_misses += 1
        logger.info(
            "ai_cache_miss",
            provider=provider,
            model=model,
            prompt_version=prompt_version
        )

    def record_retry(self, provider: str, model: str, prompt_version: str, attempt: int, error: str) -> None:
        with self._lock:
            self.retries += 1
        logger.warning(
            "ai_request_retry",
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            attempt=attempt,
            error=error
        )

    def record_failure(self, provider: str, model: str, prompt_version: str, duration_ms: float, error: str) -> None:
        with self._lock:
            self.failures += 1
        logger.error(
            "ai_request_failure",
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            duration_ms=round(duration_ms, 2),
            error=error
        )

    def record_success(self, provider: str, model: str, prompt_version: str, duration_ms: float) -> None:
        with self._lock:
            self.successes += 1
            self.request_durations.append(duration_ms)
        logger.info(
            "ai_request_success",
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            duration_ms=round(duration_ms, 2)
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Compile and return overall metrics report."""
        with self._lock:
            total_requests = self.successes + self.failures
            avg_duration = (
                sum(self.request_durations) / len(self.request_durations)
                if self.request_durations
                else 0.0
            )
            return {
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "retries": self.retries,
                "failures": self.failures,
                "successes": self.successes,
                "total_requests": total_requests,
                "average_duration_ms": round(avg_duration, 2),
            }

    def reset(self) -> None:
        """Reset all counters to zero."""
        with self._lock:
            self.cache_hits = 0
            self.cache_misses = 0
            self.retries = 0
            self.failures = 0
            self.successes = 0
            self.request_durations.clear()

# Global collector instance
ai_metrics = AIMetricsCollector()
