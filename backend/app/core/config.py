from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
import json
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "CareerPilot AI"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    API_PREFIX: str = "/api/v1"
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000"]
    LOG_LEVEL: str = "INFO"

    # Parser settings
    SPACY_MODEL: str = "en_core_web_sm"
    PARSER_VERSION: str = "v2"
    MAX_PAGES: int = 10
    MAX_TEXT_LENGTH: int = 200000

    # ATS settings
    ATS_MIN_SKILLS_FOR_FULL_SCORE: int = 8
    ATS_MIN_EXPERIENCE_ENTRIES: int = 2
    ATS_RECOMMENDATION_LIMIT: int = 8

    # Job Match settings
    JOB_MATCH_MIN_SKILLS: int = 5
    JOB_MATCH_MAX_RECOMMENDATIONS: int = 10
    JOB_MATCH_KEYWORD_LIMIT: int = 100
    JOB_MATCH_VERSION: str = "v1"

    STORAGE_PROVIDER: str = "LOCAL"
    LOCAL_STORAGE_PATH: str = "storage/resumes"
    MAX_FILE_SIZE_MB: int = 5
    ALLOWED_EXTENSIONS: list[str] = ["pdf", "docx"]
    ALLOWED_MIME_TYPES: dict = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }

    # AI settings
    AI_PROVIDER: str = "ollama"
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    AI_TEMPERATURE: float = 0.3
    AI_TOP_P: float = 0.9
    AI_MAX_TOKENS: int = 2048
    AI_TIMEOUT: int = 60
    AI_RETRY_COUNT: int = 3
    PROMPT_CACHE_ENABLED: bool = True
    PROMPT_CACHE_TTL: int = 300
    PROMPT_TEMPLATE_PATH: str = "app/ai/prompts/templates"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            try:
                # Try parsing as JSON array
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
            # Fallback to comma-separated list
            return [x.strip() for x in v.split(",") if x.strip()]
        elif isinstance(v, list):
            return [str(item) for item in v]
        return []

    @field_validator("AI_PROVIDER")
    @classmethod
    def validate_ai_provider(cls, v: str) -> str:
        valid_providers = ["ollama", "openai", "anthropic", "gemini", "groq", "together"]
        if v.lower() not in valid_providers:
            raise ValueError(f"AI_PROVIDER must be one of {valid_providers}")
        return v.lower()

    @field_validator("AI_TEMPERATURE")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("AI_TEMPERATURE must be between 0.0 and 1.0")
        return v

    @field_validator("AI_TOP_P")
    @classmethod
    def validate_top_p(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("AI_TOP_P must be between 0.0 and 1.0")
        return v

    @field_validator("AI_MAX_TOKENS", "AI_TIMEOUT")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Value must be a positive integer")
        return v

    @field_validator("AI_RETRY_COUNT", "PROMPT_CACHE_TTL")
    @classmethod
    def validate_non_negative_int(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Value must be a non-negative integer")
        return v

settings = Settings()

