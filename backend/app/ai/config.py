from app.core.config import settings

# Re-export AI settings for easier access within the AI module
AI_PROVIDER = settings.AI_PROVIDER
OLLAMA_HOST = settings.OLLAMA_HOST
OLLAMA_MODEL = settings.OLLAMA_MODEL
AI_TEMPERATURE = settings.AI_TEMPERATURE
AI_TOP_P = settings.AI_TOP_P
AI_MAX_TOKENS = settings.AI_MAX_TOKENS
AI_TIMEOUT = settings.AI_TIMEOUT
AI_RETRY_COUNT = settings.AI_RETRY_COUNT
PROMPT_CACHE_ENABLED = settings.PROMPT_CACHE_ENABLED
PROMPT_CACHE_TTL = settings.PROMPT_CACHE_TTL
PROMPT_TEMPLATE_PATH = settings.PROMPT_TEMPLATE_PATH

# Configuration-driven Review Modes
REVIEW_MODES = {
    "FAST": {
        "temperature": 0.2,
        "max_tokens": 1024,
    },
    "STANDARD": {
        "temperature": 0.2,
        "max_tokens": 2048,
    },
    "DETAILED": {
        "temperature": 0.2,
        "max_tokens": 4096,
    }
}

# Configuration-driven Rewrite Modes
REWRITE_MODES = {
    "STANDARD": {
        "temperature": 0.2,
        "max_tokens": 4096,
    },
    "PROFESSIONAL": {
        "temperature": 0.2,
        "max_tokens": 4096,
    },
    "EXECUTIVE": {
        "temperature": 0.2,
        "max_tokens": 4096,
    },
    "ATS": {
        "temperature": 0.2,
        "max_tokens": 4096,
    },
    "CONCISE": {
        "temperature": 0.2,
        "max_tokens": 2048,
    },
    "DETAILED": {
        "temperature": 0.2,
        "max_tokens": 4096,
    }
}

# Configuration-driven Optimization Modes
OPTIMIZATION_MODES = {
    "BASIC": {
        "temperature": 0.2,
        "max_tokens": 2048,
    },
    "ADVANCED": {
        "temperature": 0.2,
        "max_tokens": 4096,
    },
    "PROFESSIONAL": {
        "temperature": 0.2,
        "max_tokens": 4096,
    }
}


